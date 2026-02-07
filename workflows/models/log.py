"""Audit log model for workflow events."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UUIDMixin, TimestampMixin


class WorkflowLog(Base, UUIDMixin, TimestampMixin):
    """Audit trail entry for workflow events."""

    __tablename__ = "workflow_log"

    workflow_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("workflow.id", ondelete="SET NULL"), default=None, index=True
    )
    execution_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("workflow_execution.id", ondelete="SET NULL"), default=None
    )
    level: Mapped[str] = mapped_column(String(10), default="info")  # info/warn/error
    event: Mapped[str] = mapped_column(String(100))
    message: Mapped[str | None] = mapped_column(Text, default=None)
    data: Mapped[dict | None] = mapped_column(JSON, default=None)

    def __repr__(self) -> str:
        return f"<WorkflowLog [{self.level}] {self.event}>"
