"""Persistent auth users + invite records."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDMixin


class AuthAccount(Base, UUIDMixin, TimestampMixin):
    """Service user account used for app login + RBAC."""

    __tablename__ = "auth_account"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    invited_by_email: Mapped[str | None] = mapped_column(String(255), default=None)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    def __repr__(self) -> str:
        return f"<AuthAccount {self.email!r} ({self.role})>"


class AuthInvite(Base, UUIDMixin, TimestampMixin):
    """One-time invite for provisioning user accounts."""

    __tablename__ = "auth_invite"

    email: Mapped[str] = mapped_column(String(255), index=True)
    role: Mapped[str] = mapped_column(String(20), default="viewer")
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    invited_by_email: Mapped[str | None] = mapped_column(String(255), default=None)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    def __repr__(self) -> str:
        return f"<AuthInvite {self.email!r} ({self.role})>"


class AuthSession(Base, UUIDMixin):
    """Persisted interactive session for revocation + inventory."""

    __tablename__ = "auth_session"

    session_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    source_ip: Mapped[str | None] = mapped_column(String(64), default=None)
    user_agent: Mapped[str | None] = mapped_column(String(512), default=None)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, index=True)
    revoked_reason: Mapped[str | None] = mapped_column(String(64), default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<AuthSession {self.email!r}>"


class AuthPasswordReset(Base, UUIDMixin, TimestampMixin):
    """One-time password reset token state."""

    __tablename__ = "auth_password_reset"

    email: Mapped[str] = mapped_column(String(255), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, index=True)
    source_ip: Mapped[str | None] = mapped_column(String(64), default=None)
    user_agent: Mapped[str | None] = mapped_column(String(512), default=None)

    def __repr__(self) -> str:
        return f"<AuthPasswordReset {self.email!r}>"


class AuthEvent(Base, UUIDMixin):
    """Append-only auth audit event."""

    __tablename__ = "auth_event"

    action: Mapped[str] = mapped_column(String(64), index=True)
    outcome: Mapped[str] = mapped_column(String(24), index=True)
    actor_email: Mapped[str | None] = mapped_column(String(255), default=None, index=True)
    target_email: Mapped[str | None] = mapped_column(String(255), default=None, index=True)
    source_ip: Mapped[str | None] = mapped_column(String(64), default=None)
    user_agent: Mapped[str | None] = mapped_column(String(512), default=None)
    details_json: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<AuthEvent {self.action!r} {self.outcome!r}>"
