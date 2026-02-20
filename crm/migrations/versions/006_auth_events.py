"""Add auth audit events table.

Revision ID: 006_auth_events
Revises: 005_auth_accounts_invites
Create Date: 2026-02-20
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "006_auth_events"
down_revision: Union[str, Sequence[str], None] = "005_auth_accounts_invites"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def _has_index(bind, table_name: str, index_name: str) -> bool:
    indexes = sa.inspect(bind).get_indexes(table_name)
    return any(idx.get("name") == index_name for idx in indexes)


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_table(bind, "auth_event"):
        op.create_table(
            "auth_event",
            sa.Column("action", sa.String(length=64), nullable=False),
            sa.Column("outcome", sa.String(length=24), nullable=False),
            sa.Column("actor_email", sa.String(length=255), nullable=True),
            sa.Column("target_email", sa.String(length=255), nullable=True),
            sa.Column("source_ip", sa.String(length=64), nullable=True),
            sa.Column("user_agent", sa.String(length=512), nullable=True),
            sa.Column("details_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    if _has_table(bind, "auth_event") and not _has_index(bind, "auth_event", "ix_auth_event_action"):
        op.create_index("ix_auth_event_action", "auth_event", ["action"], unique=False)
    if _has_table(bind, "auth_event") and not _has_index(bind, "auth_event", "ix_auth_event_outcome"):
        op.create_index("ix_auth_event_outcome", "auth_event", ["outcome"], unique=False)
    if _has_table(bind, "auth_event") and not _has_index(bind, "auth_event", "ix_auth_event_actor_email"):
        op.create_index("ix_auth_event_actor_email", "auth_event", ["actor_email"], unique=False)
    if _has_table(bind, "auth_event") and not _has_index(bind, "auth_event", "ix_auth_event_target_email"):
        op.create_index("ix_auth_event_target_email", "auth_event", ["target_email"], unique=False)
    if _has_table(bind, "auth_event") and not _has_index(bind, "auth_event", "ix_auth_event_created_at"):
        op.create_index("ix_auth_event_created_at", "auth_event", ["created_at"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "auth_event"):
        op.drop_table("auth_event")
