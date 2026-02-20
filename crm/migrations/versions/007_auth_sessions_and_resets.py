"""Add auth sessions and password reset tables.

Revision ID: 007_auth_sessions_and_resets
Revises: 006_auth_events
Create Date: 2026-02-20
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "007_auth_sessions_and_resets"
down_revision: Union[str, Sequence[str], None] = "006_auth_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def _has_index(bind, table_name: str, index_name: str) -> bool:
    indexes = sa.inspect(bind).get_indexes(table_name)
    return any(idx.get("name") == index_name for idx in indexes)


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_table(bind, "auth_session"):
        op.create_table(
            "auth_session",
            sa.Column("session_id", sa.String(length=64), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("source_ip", sa.String(length=64), nullable=True),
            sa.Column("user_agent", sa.String(length=512), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_reason", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("session_id"),
        )
    if _has_table(bind, "auth_session") and not _has_index(bind, "auth_session", "ix_auth_session_session_id"):
        op.create_index("ix_auth_session_session_id", "auth_session", ["session_id"], unique=True)
    if _has_table(bind, "auth_session") and not _has_index(bind, "auth_session", "ix_auth_session_email"):
        op.create_index("ix_auth_session_email", "auth_session", ["email"], unique=False)
    if _has_table(bind, "auth_session") and not _has_index(bind, "auth_session", "ix_auth_session_expires_at"):
        op.create_index("ix_auth_session_expires_at", "auth_session", ["expires_at"], unique=False)
    if _has_table(bind, "auth_session") and not _has_index(bind, "auth_session", "ix_auth_session_last_seen_at"):
        op.create_index("ix_auth_session_last_seen_at", "auth_session", ["last_seen_at"], unique=False)
    if _has_table(bind, "auth_session") and not _has_index(bind, "auth_session", "ix_auth_session_revoked_at"):
        op.create_index("ix_auth_session_revoked_at", "auth_session", ["revoked_at"], unique=False)
    if _has_table(bind, "auth_session") and not _has_index(bind, "auth_session", "ix_auth_session_created_at"):
        op.create_index("ix_auth_session_created_at", "auth_session", ["created_at"], unique=False)

    if not _has_table(bind, "auth_password_reset"):
        op.create_table(
            "auth_password_reset",
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("source_ip", sa.String(length=64), nullable=True),
            sa.Column("user_agent", sa.String(length=512), nullable=True),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token_hash"),
        )
    if _has_table(bind, "auth_password_reset") and not _has_index(bind, "auth_password_reset", "ix_auth_password_reset_email"):
        op.create_index("ix_auth_password_reset_email", "auth_password_reset", ["email"], unique=False)
    if _has_table(bind, "auth_password_reset") and not _has_index(bind, "auth_password_reset", "ix_auth_password_reset_token_hash"):
        op.create_index("ix_auth_password_reset_token_hash", "auth_password_reset", ["token_hash"], unique=True)
    if _has_table(bind, "auth_password_reset") and not _has_index(bind, "auth_password_reset", "ix_auth_password_reset_expires_at"):
        op.create_index("ix_auth_password_reset_expires_at", "auth_password_reset", ["expires_at"], unique=False)
    if _has_table(bind, "auth_password_reset") and not _has_index(bind, "auth_password_reset", "ix_auth_password_reset_used_at"):
        op.create_index("ix_auth_password_reset_used_at", "auth_password_reset", ["used_at"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "auth_password_reset"):
        op.drop_table("auth_password_reset")
    if _has_table(bind, "auth_session"):
        op.drop_table("auth_session")
