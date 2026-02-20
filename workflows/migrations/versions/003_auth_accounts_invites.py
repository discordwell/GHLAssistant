"""Add persistent auth accounts and invites.

Revision ID: 003_auth_accounts_invites
Revises: 002_workflow_dispatch_queue
Create Date: 2026-02-18
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "003_auth_accounts_invites"
down_revision: Union[str, Sequence[str], None] = "002_workflow_dispatch_queue"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def _has_index(bind, table_name: str, index_name: str) -> bool:
    indexes = sa.inspect(bind).get_indexes(table_name)
    return any(idx.get("name") == index_name for idx in indexes)


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_table(bind, "auth_account"):
        op.create_table(
            "auth_account",
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("role", sa.String(length=20), nullable=False, server_default="viewer"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("invited_by_email", sa.String(length=255), nullable=True),
            sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("email"),
        )
    if _has_table(bind, "auth_account") and not _has_index(bind, "auth_account", "ix_auth_account_email"):
        op.create_index("ix_auth_account_email", "auth_account", ["email"], unique=True)

    if not _has_table(bind, "auth_invite"):
        op.create_table(
            "auth_invite",
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("role", sa.String(length=20), nullable=False, server_default="viewer"),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("invited_by_email", sa.String(length=255), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token_hash"),
        )
    if _has_table(bind, "auth_invite") and not _has_index(bind, "auth_invite", "ix_auth_invite_email"):
        op.create_index("ix_auth_invite_email", "auth_invite", ["email"], unique=False)
    if _has_table(bind, "auth_invite") and not _has_index(bind, "auth_invite", "ix_auth_invite_token_hash"):
        op.create_index("ix_auth_invite_token_hash", "auth_invite", ["token_hash"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "auth_invite"):
        op.drop_table("auth_invite")
    if _has_table(bind, "auth_account"):
        op.drop_table("auth_account")

