"""Initial workflows schema.

Revision ID: 001_workflows_initial
Revises:
Create Date: 2026-02-18

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001_workflows_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def _has_index(bind, table_name: str, index_name: str) -> bool:
    indexes = sa.inspect(bind).get_indexes(table_name)
    return any(idx.get("name") == index_name for idx in indexes)


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_table(bind, "workflow"):
        op.create_table(
            "workflow",
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
            sa.Column("trigger_type", sa.String(length=50), nullable=True),
            sa.Column("trigger_config", sa.JSON(), nullable=True),
            sa.Column("ghl_location_id", sa.String(length=100), nullable=True),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_table(bind, "workflow_step"):
        op.create_table(
            "workflow_step",
            sa.Column("workflow_id", sa.Uuid(), nullable=False),
            sa.Column("step_type", sa.String(length=20), nullable=False),
            sa.Column("action_type", sa.String(length=50), nullable=True),
            sa.Column("config", sa.JSON(), nullable=True),
            sa.Column("label", sa.String(length=200), nullable=True),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("canvas_x", sa.Float(), nullable=False, server_default="300"),
            sa.Column("canvas_y", sa.Float(), nullable=False, server_default="100"),
            sa.Column("next_step_id", sa.Uuid(), nullable=True),
            sa.Column("true_branch_step_id", sa.Uuid(), nullable=True),
            sa.Column("false_branch_step_id", sa.Uuid(), nullable=True),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["false_branch_step_id"], ["workflow_step.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["next_step_id"], ["workflow_step.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["true_branch_step_id"], ["workflow_step.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["workflow_id"], ["workflow.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    if _has_table(bind, "workflow_step") and not _has_index(bind, "workflow_step", "ix_workflow_step_workflow_id"):
        op.create_index("ix_workflow_step_workflow_id", "workflow_step", ["workflow_id"], unique=False)

    if not _has_table(bind, "workflow_execution"):
        op.create_table(
            "workflow_execution",
            sa.Column("workflow_id", sa.Uuid(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="running"),
            sa.Column("trigger_data", sa.JSON(), nullable=True),
            sa.Column("context_data", sa.JSON(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("steps_completed", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["workflow_id"], ["workflow.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    if _has_table(bind, "workflow_execution") and not _has_index(
        bind, "workflow_execution", "ix_workflow_execution_workflow_id"
    ):
        op.create_index(
            "ix_workflow_execution_workflow_id",
            "workflow_execution",
            ["workflow_id"],
            unique=False,
        )

    if not _has_table(bind, "workflow_step_execution"):
        op.create_table(
            "workflow_step_execution",
            sa.Column("execution_id", sa.Uuid(), nullable=False),
            sa.Column("step_id", sa.Uuid(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("input_data", sa.JSON(), nullable=True),
            sa.Column("output_data", sa.JSON(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["execution_id"], ["workflow_execution.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["step_id"], ["workflow_step.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
    if _has_table(bind, "workflow_step_execution") and not _has_index(
        bind, "workflow_step_execution", "ix_workflow_step_execution_execution_id"
    ):
        op.create_index(
            "ix_workflow_step_execution_execution_id",
            "workflow_step_execution",
            ["execution_id"],
            unique=False,
        )

    if not _has_table(bind, "workflow_log"):
        op.create_table(
            "workflow_log",
            sa.Column("workflow_id", sa.Uuid(), nullable=True),
            sa.Column("execution_id", sa.Uuid(), nullable=True),
            sa.Column("level", sa.String(length=10), nullable=False, server_default="info"),
            sa.Column("event", sa.String(length=100), nullable=False),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("data", sa.JSON(), nullable=True),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["execution_id"], ["workflow_execution.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["workflow_id"], ["workflow.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
    if _has_table(bind, "workflow_log") and not _has_index(bind, "workflow_log", "ix_workflow_log_workflow_id"):
        op.create_index("ix_workflow_log_workflow_id", "workflow_log", ["workflow_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "workflow_log"):
        op.drop_table("workflow_log")
    if _has_table(bind, "workflow_step_execution"):
        op.drop_table("workflow_step_execution")
    if _has_table(bind, "workflow_execution"):
        op.drop_table("workflow_execution")
    if _has_table(bind, "workflow_step"):
        op.drop_table("workflow_step")
    if _has_table(bind, "workflow"):
        op.drop_table("workflow")

