"""Workflow and WorkflowStep models."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, JSON, String, Text, Uuid, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from .execution import WorkflowExecution


class Workflow(Base, UUIDMixin, TimestampMixin):
    """A workflow automation definition."""

    __tablename__ = "workflow"

    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft/published/paused
    trigger_type: Mapped[str | None] = mapped_column(String(50), default=None)
    trigger_config: Mapped[dict | None] = mapped_column(JSON, default=None)
    ghl_location_id: Mapped[str | None] = mapped_column(String(100), default=None)

    steps: Mapped[list[WorkflowStep]] = relationship(
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="WorkflowStep.position",
    )
    executions: Mapped[list[WorkflowExecution]] = relationship(
        back_populates="workflow",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Workflow {self.name!r} ({self.status})>"


class WorkflowStep(Base, UUIDMixin, TimestampMixin):
    """A single step in a workflow (action, condition, or delay)."""

    __tablename__ = "workflow_step"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workflow.id", ondelete="CASCADE"), index=True
    )
    step_type: Mapped[str] = mapped_column(String(20))  # action/condition/delay
    action_type: Mapped[str | None] = mapped_column(String(50), default=None)
    config: Mapped[dict | None] = mapped_column(JSON, default=None)
    label: Mapped[str | None] = mapped_column(String(200), default=None)
    position: Mapped[int] = mapped_column(Integer, default=0)

    # Canvas position for visual editor
    canvas_x: Mapped[float] = mapped_column(Float, default=300.0)
    canvas_y: Mapped[float] = mapped_column(Float, default=100.0)

    # Flow control: next step, or branching for conditions
    next_step_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("workflow_step.id", ondelete="SET NULL", use_alter=True), default=None
    )
    true_branch_step_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("workflow_step.id", ondelete="SET NULL", use_alter=True), default=None
    )
    false_branch_step_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("workflow_step.id", ondelete="SET NULL", use_alter=True), default=None
    )

    workflow: Mapped[Workflow] = relationship(back_populates="steps")

    def __repr__(self) -> str:
        return f"<WorkflowStep {self.step_type}:{self.action_type} pos={self.position}>"
