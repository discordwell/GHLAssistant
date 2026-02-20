"""Persistent auth account + invite service."""

from __future__ import annotations

import inspect
import json
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from maxlevel.platform_auth import (
    ROLE_ORDER,
    AuthUser,
    hash_password_async,
    hash_invite_token,
    issue_invite_token,
    verify_password_async,
)

from ..config import settings
from ..database import async_session_factory, get_db
from ..models.auth import AuthAccount, AuthEvent, AuthInvite, AuthPasswordReset, AuthSession


def _normalize_role(role: str) -> str:
    role_norm = (role or "").strip().lower()
    return role_norm if role_norm in ROLE_ORDER else "viewer"


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _role_rank(role: str) -> int:
    return ROLE_ORDER.index(_normalize_role(role))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _should_update_last_login(last_login_at: datetime | None, now: datetime) -> bool:
    """Avoid hot-write amplification during rapid repeated logins."""
    last = _as_utc(last_login_at)
    if last is None:
        return True
    return (now - last).total_seconds() >= 60


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _client_ip(request: Request | None) -> str | None:
    if not request:
        return None
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    if forwarded:
        return forwarded[:64]
    if request.client and request.client.host:
        return str(request.client.host)[:64]
    return None


def _details_json(details) -> str | None:
    if details is None:
        return None
    try:
        encoded = json.dumps(details, separators=(",", ":"), sort_keys=True)
    except Exception:
        encoded = json.dumps({"value": str(details)})
    return encoded[:8192]


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


async def has_active_owner(request: Request | None = None) -> bool:
    async with _db_session(request) as db:
        count = int(
            (
                await db.execute(
                    select(func.count(AuthAccount.id)).where(
                        AuthAccount.role == "owner",
                        AuthAccount.is_active.is_(True),
                    )
                )
            ).scalar_one()
            or 0
        )
        return count > 0


async def bootstrap_owner(
    email: str,
    password: str,
    role: str = "owner",
    force: bool = False,
    request: Request | None = None,
) -> bool:
    email_norm = _normalize_email(email)
    if not email_norm or len(password or "") < 8:
        return False

    role_norm = _normalize_role(role)
    if role_norm != "owner":
        role_norm = "owner"

    async with _db_session(request) as db:
        account = (
            await db.execute(select(AuthAccount).where(AuthAccount.email == email_norm))
        ).scalar_one_or_none()
        if account:
            if not force:
                return False
            account.password_hash = await hash_password_async(password)
            account.role = "owner"
            account.is_active = True
        else:
            db.add(
                AuthAccount(
                    email=email_norm,
                    password_hash=await hash_password_async(password),
                    role="owner",
                    is_active=True,
                )
            )
        await db.commit()
        return True


async def authenticate_user(
    email: str,
    password: str,
    request: Request | None = None,
) -> AuthUser | None:
    """Validate credentials against persistent users."""
    email_norm = _normalize_email(email)
    if not email_norm or not password:
        return None

    async with _db_session(request) as db:
        account = (
            await db.execute(select(AuthAccount).where(AuthAccount.email == email_norm))
        ).scalar_one_or_none()
        if not account or not account.is_active:
            return None
        if not await verify_password_async(password, account.password_hash):
            return None

        now = _utcnow()
        if _should_update_last_login(account.last_login_at, now):
            account.last_login_at = now
            await db.commit()
        return AuthUser(email=account.email, role=account.role)


async def resolve_user(email: str, request: Request | None = None) -> AuthUser | None:
    email_norm = _normalize_email(email)
    if not email_norm:
        return None

    async with _db_session(request) as db:
        account = (
            await db.execute(select(AuthAccount).where(AuthAccount.email == email_norm))
        ).scalar_one_or_none()
        if not account or not account.is_active:
            return None
        return AuthUser(email=account.email, role=_normalize_role(account.role))


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


async def list_accounts(limit: int = 200, request: Request | None = None) -> list[dict]:
    async with _db_session(request) as db:
        accounts = list(
            (
                await db.execute(
                    select(AuthAccount).order_by(AuthAccount.created_at.desc()).limit(limit)
                )
            )
            .scalars()
            .all()
        )

    rows = []
    for account in accounts:
        rows.append(
            {
                "email": account.email,
                "role": account.role,
                "is_active": account.is_active,
                "last_login_at": _as_utc(account.last_login_at),
                "created_at": _as_utc(account.created_at),
            }
        )
    return rows


async def _active_owner_count_excluding(
    db: AsyncSession,
    email_exclude: str,
) -> int:
    return int(
        (
            await db.execute(
                select(func.count(AuthAccount.id)).where(
                    AuthAccount.role == "owner",
                    AuthAccount.is_active.is_(True),
                    AuthAccount.email != email_exclude,
                )
            )
        ).scalar_one()
        or 0
    )


async def update_account(
    email: str,
    role: str,
    is_active: bool,
    actor_email: str | None,
    actor_role: str | None = None,
    request: Request | None = None,
) -> bool:
    email_norm = _normalize_email(email)
    actor_norm = _normalize_email(actor_email or "")
    actor_role_norm = _normalize_role(actor_role or "")
    if not email_norm:
        return False
    if not actor_norm or not actor_role:
        return False

    async with _db_session(request) as db:
        account = (
            await db.execute(select(AuthAccount).where(AuthAccount.email == email_norm))
        ).scalar_one_or_none()
        if not account:
            return False

        next_role = _normalize_role(role)
        current_role = _normalize_role(account.role)

        if actor_norm == email_norm and not is_active:
            return False
        if actor_norm == email_norm and next_role != current_role:
            return False

        actor_rank = _role_rank(actor_role_norm)
        current_rank = _role_rank(current_role)
        next_rank = _role_rank(next_role)
        if actor_norm != email_norm and actor_role_norm != "owner":
            if actor_rank <= current_rank:
                return False
            if next_rank >= actor_rank:
                return False

        removing_owner = current_role == "owner" and (next_role != "owner" or not is_active)
        if removing_owner:
            if await _active_owner_count_excluding(db, email_norm) < 1:
                return False

        account.role = next_role
        account.is_active = bool(is_active)
        await db.commit()
        return True


async def change_password(
    email: str,
    current_password: str,
    new_password: str,
    request: Request | None = None,
) -> bool:
    email_norm = _normalize_email(email)
    if not email_norm or len(new_password or "") < 8:
        return False

    async with _db_session(request) as db:
        account = (
            await db.execute(select(AuthAccount).where(AuthAccount.email == email_norm))
        ).scalar_one_or_none()
        if not account or not account.is_active:
            return False
        if not await verify_password_async(current_password or "", account.password_hash):
            return False

        account.password_hash = await hash_password_async(new_password)
        await db.commit()
        return True


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

        hashed = await hash_password_async(password)
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


async def record_auth_event(
    action: str,
    outcome: str,
    actor_email: str | None = None,
    target_email: str | None = None,
    details=None,
    request: Request | None = None,
) -> None:
    action_norm = (action or "").strip().lower()[:64]
    outcome_norm = (outcome or "").strip().lower()[:24]
    if not action_norm or not outcome_norm:
        return

    async with _db_session(request) as db:
        db.add(
            AuthEvent(
                action=action_norm,
                outcome=outcome_norm,
                actor_email=_normalize_email(actor_email or "") or None,
                target_email=_normalize_email(target_email or "") or None,
                source_ip=_client_ip(request),
                user_agent=(request.headers.get("user-agent", "")[:512] if request else None),
                details_json=_details_json(details),
            )
        )
        await db.commit()


async def list_auth_events(limit: int = 200, request: Request | None = None) -> list[dict]:
    async with _db_session(request) as db:
        rows = list(
            (
                await db.execute(
                    select(AuthEvent).order_by(AuthEvent.created_at.desc()).limit(max(1, min(limit, 1000)))
                )
            )
            .scalars()
            .all()
        )
    return [
        {
            "created_at": _as_utc(row.created_at),
            "action": row.action,
            "outcome": row.outcome,
            "actor_email": row.actor_email,
            "target_email": row.target_email,
            "source_ip": row.source_ip,
        }
        for row in rows
    ]


async def create_session(
    email: str,
    session_id: str,
    expires_at: datetime,
    request: Request | None = None,
) -> bool:
    email_norm = _normalize_email(email)
    sid = (session_id or "").strip()[:64]
    if not email_norm or not sid:
        return False
    async with _db_session(request) as db:
        db.add(
            AuthSession(
                session_id=sid,
                email=email_norm,
                source_ip=_client_ip(request),
                user_agent=(request.headers.get("user-agent", "")[:512] if request else None),
                expires_at=_as_utc(expires_at) or _utcnow(),
                last_seen_at=_utcnow(),
            )
        )
        await db.commit()
        return True


async def validate_session(
    email: str,
    session_id: str,
    request: Request | None = None,
) -> bool:
    email_norm = _normalize_email(email)
    sid = (session_id or "").strip()[:64]
    if not email_norm or not sid:
        return False
    now = _utcnow()
    async with _db_session(request) as db:
        sess = (
            await db.execute(
                select(AuthSession).where(
                    AuthSession.email == email_norm,
                    AuthSession.session_id == sid,
                )
            )
        ).scalar_one_or_none()
        if not sess:
            return False
        if sess.revoked_at is not None:
            return False
        if (_as_utc(sess.expires_at) or now) <= now:
            return False
        sess.last_seen_at = now
        await db.commit()
        return True


async def list_sessions(email: str, request: Request | None = None, limit: int = 100) -> list[dict]:
    email_norm = _normalize_email(email)
    if not email_norm:
        return []
    async with _db_session(request) as db:
        sessions = list(
            (
                await db.execute(
                    select(AuthSession)
                    .where(
                        AuthSession.email == email_norm,
                        AuthSession.revoked_at.is_(None),
                        AuthSession.expires_at > _utcnow(),
                    )
                    .order_by(AuthSession.created_at.desc())
                    .limit(max(1, min(limit, 500)))
                )
            )
            .scalars()
            .all()
        )
    return [
        {
            "session_id": sess.session_id,
            "source_ip": sess.source_ip,
            "created_at": _as_utc(sess.created_at),
            "last_seen_at": _as_utc(sess.last_seen_at),
            "expires_at": _as_utc(sess.expires_at),
        }
        for sess in sessions
    ]


async def revoke_session(
    email: str,
    session_id: str,
    actor_email: str | None = None,
    request: Request | None = None,
) -> bool:
    email_norm = _normalize_email(email)
    sid = (session_id or "").strip()[:64]
    actor_norm = _normalize_email(actor_email or "")
    if not email_norm or not sid:
        return False
    if actor_norm and actor_norm != email_norm:
        return False

    async with _db_session(request) as db:
        sess = (
            await db.execute(
                select(AuthSession).where(
                    AuthSession.email == email_norm,
                    AuthSession.session_id == sid,
                )
            )
        ).scalar_one_or_none()
        if not sess or sess.revoked_at is not None:
            return False
        sess.revoked_at = _utcnow()
        sess.revoked_reason = "manual_logout"
        await db.commit()
        return True


async def revoke_all_sessions(
    email: str,
    actor_email: str | None = None,
    keep_session_id: str = "",
    request: Request | None = None,
) -> int:
    email_norm = _normalize_email(email)
    actor_norm = _normalize_email(actor_email or "")
    keep_sid = (keep_session_id or "").strip()[:64]
    if not email_norm:
        return 0
    if actor_norm and actor_norm != email_norm:
        return 0
    async with _db_session(request) as db:
        sessions = list(
            (
                await db.execute(
                    select(AuthSession).where(
                        AuthSession.email == email_norm,
                        AuthSession.revoked_at.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        count = 0
        now = _utcnow()
        for sess in sessions:
            if keep_sid and sess.session_id == keep_sid:
                continue
            sess.revoked_at = now
            sess.revoked_reason = "logout_all"
            count += 1
        await db.commit()
        return count


def _hash_reset_token(token: str) -> str:
    return hash_invite_token(token)


async def request_password_reset(
    email: str,
    request: Request | None = None,
) -> str | None:
    email_norm = _normalize_email(email)
    if not email_norm:
        return None

    async with _db_session(request) as db:
        account = (
            await db.execute(
                select(AuthAccount).where(
                    AuthAccount.email == email_norm,
                    AuthAccount.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if not account:
            return None

        now = _utcnow()
        existing = list(
            (
                await db.execute(
                    select(AuthPasswordReset).where(
                        AuthPasswordReset.email == email_norm,
                        AuthPasswordReset.used_at.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        for row in existing:
            row.used_at = now

        token = secrets.token_urlsafe(32)
        db.add(
            AuthPasswordReset(
                email=email_norm,
                token_hash=_hash_reset_token(token),
                expires_at=now + timedelta(minutes=60),
                source_ip=_client_ip(request),
                user_agent=(request.headers.get("user-agent", "")[:512] if request else None),
            )
        )
        await db.commit()
        return token


async def reset_password(
    token: str,
    new_password: str,
    request: Request | None = None,
) -> AuthUser | None:
    if len(new_password or "") < 8:
        return None
    token_hash = _hash_reset_token(token or "")
    now = _utcnow()
    async with _db_session(request) as db:
        row = (
            await db.execute(select(AuthPasswordReset).where(AuthPasswordReset.token_hash == token_hash))
        ).scalar_one_or_none()
        if (
            not row
            or row.used_at is not None
            or (_as_utc(row.expires_at) or now) <= now
        ):
            return None
        account = (
            await db.execute(
                select(AuthAccount).where(
                    AuthAccount.email == row.email,
                    AuthAccount.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if not account:
            return None
        account.password_hash = await hash_password_async(new_password)
        account.last_login_at = now
        row.used_at = now
        await db.commit()
        return AuthUser(email=account.email, role=account.role)
