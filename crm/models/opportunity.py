"""Opportunity model - deals in pipeline stages."""

from __future__ import annotations

import uuid

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDMixin, TimestampMixin, TenantMixin, GHLSyncMixin


class Opportunity(UUIDMixin, TimestampMixin, TenantMixin, GHLSyncMixin, Base):
    __tablename__ = "opportunity"

    name: Mapped[str] = mapped_column(String(300))
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("pipeline.id", ondelete="CASCADE"), index=True
    )
    stage_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("pipeline_stage.id", ondelete="SET NULL"),
        nullable=True, index=True
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("contact.id", ondelete="SET NULL"),
        default=None, index=True
    )
    monetary_value: Mapped[float | None] = mapped_column(Float, default=None)
    status: Mapped[str] = mapped_column(String(50), default="open")  # open, won, lost, abandoned
    source: Mapped[str | None] = mapped_column(String(100), default=None)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    # Relationships
    pipeline: Mapped["Pipeline"] = relationship(back_populates="opportunities")  # noqa: F821
    stage: Mapped["PipelineStage | None"] = relationship(  # noqa: F821
        back_populates="opportunities"
    )
    contact: Mapped["Contact | None"] = relationship(back_populates="opportunities")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Opportunity {self.name!r}>"
