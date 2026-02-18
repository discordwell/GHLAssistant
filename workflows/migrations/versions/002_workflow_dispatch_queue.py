"""Add workflow dispatch queue table.

Revision ID: 002_workflow_dispatch_queue
Revises: 001_workflows_initial
Create Date: 2026-02-18

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "002_workflow_dispatch_queue"
down_revision: Union[str, Sequence[str], None] = "001_workflows_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def _has_index(bind, table_name: str, index_name: str) -> bool:
    indexes = sa.inspect(bind).get_indexes(table_name)
    return any(idx.get("name") == index_name for idx in indexes)


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_table(bind, "workflow_dispatch"):
        op.create_table(
            "workflow_dispatch",
            sa.Column("workflow_id", sa.Uuid(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("trigger_data", sa.JSON(), nullable=True),
            sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("execution_id", sa.Uuid(), nullable=True),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["execution_id"], ["workflow_execution.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["workflow_id"], ["workflow.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    if _has_table(bind, "workflow_dispatch") and not _has_index(
        bind, "workflow_dispatch", "ix_workflow_dispatch_workflow_id"
    ):
        op.create_index(
            "ix_workflow_dispatch_workflow_id",
            "workflow_dispatch",
            ["workflow_id"],
            unique=False,
        )
    if _has_table(bind, "workflow_dispatch") and not _has_index(
        bind, "workflow_dispatch", "ix_workflow_dispatch_available_at"
    ):
        op.create_index(
            "ix_workflow_dispatch_available_at",
            "workflow_dispatch",
            ["available_at"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "workflow_dispatch"):
        op.drop_table("workflow_dispatch")

