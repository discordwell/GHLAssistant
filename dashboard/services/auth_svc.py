"""Dashboard auth adapter backed by CRM auth tables."""

from __future__ import annotations

import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from maxlevel.platform_auth import (
    ROLE_ORDER,
    AuthUser,
    hash_invite_token,
    hash_password_async,
    verify_password_async,
)

from .. import database as db_module


def _normalize_role(role: str) -> str:
    role_norm = (role or "").strip().lower()
    return role_norm if role_norm in ROLE_ORDER else "viewer"


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _should_update_last_login(last_login_at: datetime | None, now: datetime) -> bool:
    """Avoid hot-write amplification during rapid repeated logins."""
    if not isinstance(last_login_at, datetime):
        return True
    return (now - last_login_at).total_seconds() >= 60


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


async def has_active_owner(request: Request | None = None) -> bool:
    async with db_module.multi_db.crm_session() as db:
        try:
            count = (
                await db.execute(
                    text(
                        """
                        SELECT COUNT(*) AS c
                        FROM auth_account
                        WHERE role = 'owner' AND is_active = 1
                        """
                    )
                )
            ).scalar_one()
            return int(count or 0) > 0
        except SQLAlchemyError:
            return False


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
                        SELECT email, password_hash, role, is_active, last_login_at
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
            if not await verify_password_async(password, str(row.get("password_hash", ""))):
                return None

            if _should_update_last_login(row.get("last_login_at"), now):
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


async def list_auth_events(limit: int = 200, request: Request | None = None) -> list[dict]:
    async with db_module.multi_db.crm_session() as db:
        try:
            rows = (
                await db.execute(
                    text(
                        """
                        SELECT created_at, action, outcome, actor_email, target_email, source_ip
                        FROM auth_event
                        ORDER BY created_at DESC
                        LIMIT :limit
                        """
                    ),
                    {"limit": max(1, min(limit, 1000))},
                )
            ).mappings().all()
            return [dict(row) for row in rows]
        except SQLAlchemyError:
            return []


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
    async with db_module.multi_db.crm_session() as db:
        try:
            await db.execute(
                text(
                    """
                    INSERT INTO auth_session (
                        id, session_id, email, source_ip, user_agent,
                        expires_at, last_seen_at, revoked_at, revoked_reason, created_at
                    )
                    VALUES (
                        :id, :session_id, :email, :source_ip, :user_agent,
                        :expires_at, :last_seen_at, NULL, NULL, :created_at
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "session_id": sid,
                    "email": email_norm,
                    "source_ip": _client_ip(request),
                    "user_agent": (request.headers.get("user-agent", "")[:512] if request else None),
                    "expires_at": expires_at,
                    "last_seen_at": _utcnow(),
                    "created_at": _utcnow(),
                },
            )
            await db.commit()
            return True
        except SQLAlchemyError:
            await db.rollback()
            return False


async def validate_session(
    email: str,
    session_id: str,
    request: Request | None = None,
) -> bool:
    email_norm = _normalize_email(email)
    sid = (session_id or "").strip()[:64]
    if not email_norm or not sid:
        return False
    async with db_module.multi_db.crm_session() as db:
        try:
            row = (
                await db.execute(
                    text(
                        """
                        SELECT id, expires_at, revoked_at
                        FROM auth_session
                        WHERE email = :email AND session_id = :session_id
                        LIMIT 1
                        """
                    ),
                    {"email": email_norm, "session_id": sid},
                )
            ).mappings().first()
            if not row:
                return False
            if row.get("revoked_at") is not None:
                return False
            expires_at = row.get("expires_at")
            if isinstance(expires_at, datetime) and expires_at <= _utcnow():
                return False
            await db.execute(
                text("UPDATE auth_session SET last_seen_at = :last_seen_at WHERE id = :id"),
                {"last_seen_at": _utcnow(), "id": row["id"]},
            )
            await db.commit()
            return True
        except SQLAlchemyError:
            await db.rollback()
            return False


async def list_sessions(email: str, request: Request | None = None, limit: int = 100) -> list[dict]:
    email_norm = _normalize_email(email)
    if not email_norm:
        return []
    async with db_module.multi_db.crm_session() as db:
        try:
            rows = (
                await db.execute(
                    text(
                        """
                        SELECT session_id, source_ip, created_at, last_seen_at, expires_at
                        FROM auth_session
                        WHERE email = :email
                          AND revoked_at IS NULL
                          AND expires_at > :now
                        ORDER BY created_at DESC
                        LIMIT :limit
                        """
                    ),
                    {"email": email_norm, "now": _utcnow(), "limit": max(1, min(limit, 500))},
                )
            ).mappings().all()
            return [dict(row) for row in rows]
        except SQLAlchemyError:
            return []


async def revoke_session(
    email: str,
    session_id: str,
    actor_email: str | None = None,
    request: Request | None = None,
) -> bool:
    email_norm = _normalize_email(email)
    actor_norm = _normalize_email(actor_email or "")
    sid = (session_id or "").strip()[:64]
    if not email_norm or not sid:
        return False
    if actor_norm and actor_norm != email_norm:
        return False
    async with db_module.multi_db.crm_session() as db:
        try:
            result = await db.execute(
                text(
                    """
                    UPDATE auth_session
                    SET revoked_at = :revoked_at, revoked_reason = :reason
                    WHERE email = :email
                      AND session_id = :session_id
                      AND revoked_at IS NULL
                    """
                ),
                {
                    "revoked_at": _utcnow(),
                    "reason": "manual_logout",
                    "email": email_norm,
                    "session_id": sid,
                },
            )
            await db.commit()
            return int(getattr(result, "rowcount", 0) or 0) > 0
        except SQLAlchemyError:
            await db.rollback()
            return False


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
    async with db_module.multi_db.crm_session() as db:
        try:
            if keep_sid:
                result = await db.execute(
                    text(
                        """
                        UPDATE auth_session
                        SET revoked_at = :revoked_at, revoked_reason = :reason
                        WHERE email = :email
                          AND revoked_at IS NULL
                          AND session_id != :keep_session_id
                        """
                    ),
                    {
                        "revoked_at": _utcnow(),
                        "reason": "logout_all",
                        "email": email_norm,
                        "keep_session_id": keep_sid,
                    },
                )
            else:
                result = await db.execute(
                    text(
                        """
                        UPDATE auth_session
                        SET revoked_at = :revoked_at, revoked_reason = :reason
                        WHERE email = :email
                          AND revoked_at IS NULL
                        """
                    ),
                    {
                        "revoked_at": _utcnow(),
                        "reason": "logout_all",
                        "email": email_norm,
                    },
                )
            await db.commit()
            return int(getattr(result, "rowcount", 0) or 0)
        except SQLAlchemyError:
            await db.rollback()
            return 0


async def request_password_reset(
    email: str,
    request: Request | None = None,
) -> str | None:
    email_norm = _normalize_email(email)
    if not email_norm:
        return None
    async with db_module.multi_db.crm_session() as db:
        try:
            row = (
                await db.execute(
                    text(
                        """
                        SELECT email
                        FROM auth_account
                        WHERE lower(email) = :email
                          AND is_active = 1
                        LIMIT 1
                        """
                    ),
                    {"email": email_norm},
                )
            ).first()
            if not row:
                return None

            await db.execute(
                text(
                    """
                    UPDATE auth_password_reset
                    SET used_at = :used_at
                    WHERE email = :email
                      AND used_at IS NULL
                    """
                ),
                {"used_at": _utcnow(), "email": email_norm},
            )

            token = secrets.token_urlsafe(32)
            await db.execute(
                text(
                    """
                    INSERT INTO auth_password_reset (
                        id, email, token_hash, expires_at, used_at,
                        source_ip, user_agent, created_at, updated_at
                    )
                    VALUES (
                        :id, :email, :token_hash, :expires_at, NULL,
                        :source_ip, :user_agent, :created_at, :updated_at
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "email": email_norm,
                    "token_hash": hash_invite_token(token),
                    "expires_at": _utcnow() + timedelta(minutes=60),
                    "source_ip": _client_ip(request),
                    "user_agent": (request.headers.get("user-agent", "")[:512] if request else None),
                    "created_at": _utcnow(),
                    "updated_at": _utcnow(),
                },
            )
            await db.commit()
            return token
        except SQLAlchemyError:
            await db.rollback()
            return None


async def reset_password(
    token: str,
    new_password: str,
    request: Request | None = None,
) -> AuthUser | None:
    if len(new_password or "") < 8:
        return None
    token_hash = hash_invite_token(token or "")
    async with db_module.multi_db.crm_session() as db:
        try:
            reset_row = (
                await db.execute(
                    text(
                        """
                        SELECT id, email, expires_at, used_at
                        FROM auth_password_reset
                        WHERE token_hash = :token_hash
                        LIMIT 1
                        """
                    ),
                    {"token_hash": token_hash},
                )
            ).mappings().first()
            if not reset_row:
                return None
            expires_at = reset_row.get("expires_at")
            if reset_row.get("used_at") is not None:
                return None
            if isinstance(expires_at, datetime) and expires_at <= _utcnow():
                return None

            account_row = (
                await db.execute(
                    text(
                        """
                        SELECT email, role, is_active
                        FROM auth_account
                        WHERE lower(email) = :email
                        LIMIT 1
                        """
                    ),
                    {"email": _normalize_email(str(reset_row.get("email", "")))},
                )
            ).mappings().first()
            if not account_row or not bool(account_row.get("is_active", False)):
                return None

            await db.execute(
                text(
                    """
                    UPDATE auth_account
                    SET password_hash = :password_hash,
                        last_login_at = :last_login_at,
                        updated_at = :updated_at
                    WHERE lower(email) = :email
                    """
                ),
                {
                    "password_hash": await hash_password_async(new_password),
                    "last_login_at": _utcnow(),
                    "updated_at": _utcnow(),
                    "email": _normalize_email(str(account_row.get("email", ""))),
                },
            )
            await db.execute(
                text(
                    """
                    UPDATE auth_password_reset
                    SET used_at = :used_at, updated_at = :updated_at
                    WHERE id = :id
                    """
                ),
                {"used_at": _utcnow(), "updated_at": _utcnow(), "id": reset_row["id"]},
            )
            await db.commit()
            return AuthUser(
                email=_normalize_email(str(account_row.get("email", ""))),
                role=_normalize_role(str(account_row.get("role", "viewer"))),
            )
        except SQLAlchemyError:
            await db.rollback()
            return None
