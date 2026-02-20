"""Persistent auth account + invite service."""

from __future__ import annotations

import inspect
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from maxlevel.platform_auth import (
    ROLE_ORDER,
    AuthUser,
    hash_invite_token,
    hash_password,
    issue_invite_token,
    verify_password,
)

from ..config import settings
from ..database import async_session_factory, get_db
from ..models.auth import AuthAccount, AuthInvite


def _normalize_role(role: str) -> str:
    role_norm = (role or "").strip().lower()
    return role_norm if role_norm in ROLE_ORDER else "viewer"


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@asynccontextmanager
async def _db_session(request: Request | None = None):
    if request is None:
        async with async_session_factory() as db:
            yield db
        return

    provider = request.app.dependency_overrides.get(get_db, get_db)
    dep = provider()
    if inspect.isasyncgen(dep):
        db = await dep.__anext__()
        try:
            yield db
        finally:
            await dep.aclose()
        return

    if inspect.isawaitable(dep):
        db = await dep
        try:
            yield db
        finally:
            close = getattr(db, "close", None)
            if close:
                maybe = close()
                if inspect.isawaitable(maybe):
                    await maybe
        return

    if isinstance(dep, AsyncSession):
        try:
            yield dep
        finally:
            await dep.close()
        return

    raise RuntimeError("Unsupported DB dependency provider for auth service")


async def _ensure_bootstrap_account(request: Request | None = None) -> None:
    email = _normalize_email(settings.auth_bootstrap_email)
    password = settings.auth_bootstrap_password
    if not email or not password:
        return

    async with _db_session(request) as db:
        account = (
            await db.execute(select(AuthAccount).where(AuthAccount.email == email))
        ).scalar_one_or_none()
        if account:
            return
        db.add(
            AuthAccount(
                email=email,
                password_hash=hash_password(password),
                role=_normalize_role(settings.auth_bootstrap_role),
                is_active=True,
            )
        )
        await db.commit()


async def authenticate_user(
    email: str,
    password: str,
    request: Request | None = None,
) -> AuthUser | None:
    """Validate credentials against persistent users."""
    await _ensure_bootstrap_account(request)

    email_norm = _normalize_email(email)
    if not email_norm or not password:
        return None

    async with _db_session(request) as db:
        account = (
            await db.execute(select(AuthAccount).where(AuthAccount.email == email_norm))
        ).scalar_one_or_none()
        if not account or not account.is_active:
            return None
        if not verify_password(password, account.password_hash):
            return None

        account.last_login_at = _utcnow()
        await db.commit()
        return AuthUser(email=account.email, role=account.role)


async def list_invites(limit: int = 100, request: Request | None = None) -> list[dict]:
    """List invite records for admin UI."""
    async with _db_session(request) as db:
        invites = list(
            (
                await db.execute(
                    select(AuthInvite).order_by(AuthInvite.created_at.desc()).limit(limit)
                )
            )
            .scalars()
            .all()
        )

    now = _utcnow()
    rows = []
    for inv in invites:
        expires_at = _as_utc(inv.expires_at) or _utcnow()
        if inv.revoked_at:
            status = "revoked"
        elif inv.accepted_at:
            status = "accepted"
        elif expires_at <= now:
            status = "expired"
        else:
            status = "pending"
        rows.append(
            {
                "email": inv.email,
                "role": inv.role,
                "status": status,
                "expires_at": expires_at,
            }
        )
    return rows


async def create_invite(
    email: str,
    role: str,
    invited_by_email: str | None,
    request: Request | None = None,
) -> str:
    """Create a one-time invite token."""
    email_norm = _normalize_email(email)
    if not email_norm:
        raise ValueError("Email is required")

    now = _utcnow()
    token = issue_invite_token()
    token_hash = hash_invite_token(token)

    async with _db_session(request) as db:
        existing = list(
            (
                await db.execute(
                    select(AuthInvite).where(
                        AuthInvite.email == email_norm,
                        AuthInvite.accepted_at.is_(None),
                        AuthInvite.revoked_at.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        for inv in existing:
            inv.revoked_at = now

        db.add(
            AuthInvite(
                email=email_norm,
                role=_normalize_role(role),
                token_hash=token_hash,
                invited_by_email=_normalize_email(invited_by_email or ""),
                expires_at=now + timedelta(hours=max(1, settings.auth_invite_ttl_hours)),
            )
        )
        await db.commit()
    return token


async def accept_invite(
    token: str,
    password: str,
    request: Request | None = None,
) -> AuthUser | None:
    """Activate invite and provision/update user account."""
    token_hash = hash_invite_token(token)
    now = _utcnow()

    async with _db_session(request) as db:
        invite = (
            await db.execute(select(AuthInvite).where(AuthInvite.token_hash == token_hash))
        ).scalar_one_or_none()
        if (
            not invite
            or invite.revoked_at is not None
            or invite.accepted_at is not None
            or (_as_utc(invite.expires_at) or now) <= now
        ):
            return None

        email = _normalize_email(invite.email)
        account = (
            await db.execute(select(AuthAccount).where(AuthAccount.email == email))
        ).scalar_one_or_none()

        hashed = hash_password(password)
        if account:
            account.password_hash = hashed
            account.role = _normalize_role(invite.role)
            account.is_active = True
            account.invited_by_email = invite.invited_by_email
        else:
            account = AuthAccount(
                email=email,
                password_hash=hashed,
                role=_normalize_role(invite.role),
                is_active=True,
                invited_by_email=invite.invited_by_email,
            )
            db.add(account)

        invite.accepted_at = now
        account.last_login_at = now
        await db.commit()
        return AuthUser(email=account.email, role=account.role)
