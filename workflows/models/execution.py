"""Execution tracking models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDMixin, TimestampMixin
from .workflow import Workflow, WorkflowStep


class WorkflowExecution(Base, UUIDMixin, TimestampMixin):
    """A single run of a workflow."""

    __tablename__ = "workflow_execution"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workflow.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default="running"
    )  # running/completed/failed/waiting
    trigger_data: Mapped[dict | None] = mapped_column(JSON, default=None)
    context_data: Mapped[dict | None] = mapped_column(JSON, default=None)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    steps_completed: Mapped[int] = mapped_column(Integer, default=0)

    workflow: Mapped[Workflow] = relationship(back_populates="executions")
    step_executions: Mapped[list[WorkflowStepExecution]] = relationship(
        back_populates="execution",
        cascade="all, delete-orphan",
        order_by="WorkflowStepExecution.created_at",
    )

    def __repr__(self) -> str:
        return f"<WorkflowExecution {self.status} steps={self.steps_completed}>"


class WorkflowStepExecution(Base, UUIDMixin, TimestampMixin):
    """Execution record for a single step within a workflow run."""

    __tablename__ = "workflow_step_execution"

    execution_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workflow_execution.id", ondelete="CASCADE"), index=True
    )
    step_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workflow_step.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending/running/completed/failed/skipped
    input_data: Mapped[dict | None] = mapped_column(JSON, default=None)
    output_data: Mapped[dict | None] = mapped_column(JSON, default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    duration_ms: Mapped[int | None] = mapped_column(Integer, default=None)

    execution: Mapped[WorkflowExecution] = relationship(back_populates="step_executions")
    step: Mapped[WorkflowStep | None] = relationship()

    def __repr__(self) -> str:
        return f"<WorkflowStepExecution {self.status}>"
