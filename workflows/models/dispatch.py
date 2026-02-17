"""Durable queue model for webhook-triggered workflow dispatches."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDMixin, TimestampMixin
from .execution import WorkflowExecution
from .workflow import Workflow


class WorkflowDispatch(Base, UUIDMixin, TimestampMixin):
    """Queue item representing a requested workflow run."""

    __tablename__ = "workflow_dispatch"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workflow.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending/running/completed/failed/retrying
    trigger_data: Mapped[dict | None] = mapped_column(JSON, default=None)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, nullable=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    execution_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("workflow_execution.id", ondelete="SET NULL"), nullable=True
    )

    workflow: Mapped[Workflow] = relationship()
    execution: Mapped[WorkflowExecution | None] = relationship()

    def __repr__(self) -> str:
        return f"<WorkflowDispatch {self.status} attempts={self.attempts}>"

