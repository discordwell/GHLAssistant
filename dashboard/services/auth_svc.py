"""Dashboard auth adapter backed by CRM auth tables."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

import uuid

from maxlevel.platform_auth import ROLE_ORDER, AuthUser, verify_password

from .. import database as db_module


def _normalize_role(role: str) -> str:
    role_norm = (role or "").strip().lower()
    return role_norm if role_norm in ROLE_ORDER else "viewer"


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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


async def authenticate_user(
    email: str,
    password: str,
    request: Request | None = None,
) -> AuthUser | None:
    email_norm = _normalize_email(email)
    if not email_norm or not password:
        return None

    now = _utcnow()
    async with db_module.multi_db.crm_session() as db:
        try:
            row = (
                await db.execute(
                    text(
                        """
                        SELECT email, password_hash, role, is_active
                        FROM auth_account
                        WHERE lower(email) = :email
                        LIMIT 1
                        """
                    ),
                    {"email": email_norm},
                )
            ).mappings().first()
            if not row:
                return None
            if not bool(row.get("is_active", False)):
                return None
            if not verify_password(password, str(row.get("password_hash", ""))):
                return None

            await db.execute(
                text(
                    """
                    UPDATE auth_account
                    SET last_login_at = :last_login_at, updated_at = :updated_at
                    WHERE lower(email) = :email
                    """
                ),
                {"last_login_at": now, "updated_at": now, "email": email_norm},
            )
            await db.commit()
            return AuthUser(
                email=_normalize_email(str(row.get("email", email_norm))),
                role=_normalize_role(str(row.get("role", "viewer"))),
            )
        except SQLAlchemyError:
            await db.rollback()
            return None


async def resolve_user(email: str, request: Request | None = None) -> AuthUser | None:
    email_norm = _normalize_email(email)
    if not email_norm:
        return None

    async with db_module.multi_db.crm_session() as db:
        try:
            row = (
                await db.execute(
                    text(
                        """
                        SELECT email, role, is_active
                        FROM auth_account
                        WHERE lower(email) = :email
                        LIMIT 1
                        """
                    ),
                    {"email": email_norm},
                )
            ).mappings().first()
            if not row or not bool(row.get("is_active", False)):
                return None
            return AuthUser(
                email=_normalize_email(str(row.get("email", email_norm))),
                role=_normalize_role(str(row.get("role", "viewer"))),
            )
        except SQLAlchemyError:
            return None


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

    async with db_module.multi_db.crm_session() as db:
        try:
            await db.execute(
                text(
                    """
                    INSERT INTO auth_event (
                        id, action, outcome, actor_email, target_email,
                        source_ip, user_agent, details_json, created_at
                    )
                    VALUES (
                        :id, :action, :outcome, :actor_email, :target_email,
                        :source_ip, :user_agent, :details_json, :created_at
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "action": action_norm,
                    "outcome": outcome_norm,
                    "actor_email": _normalize_email(actor_email or "") or None,
                    "target_email": _normalize_email(target_email or "") or None,
                    "source_ip": _client_ip(request),
                    "user_agent": (request.headers.get("user-agent", "")[:512] if request else None),
                    "details_json": _details_json(details),
                    "created_at": _utcnow(),
                },
            )
            await db.commit()
        except SQLAlchemyError:
            await db.rollback()
