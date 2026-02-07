"""Pipeline and PipelineStage models."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDMixin, TimestampMixin, TenantMixin, GHLSyncMixin


class Pipeline(UUIDMixin, TimestampMixin, TenantMixin, GHLSyncMixin, Base):
    __tablename__ = "pipeline"
    __table_args__ = (UniqueConstraint("location_id", "name", name="uq_pipeline_location_name"),)

    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(500), default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    location: Mapped["Location"] = relationship(back_populates="pipelines")  # noqa: F821
    stages: Mapped[list["PipelineStage"]] = relationship(
        back_populates="pipeline", cascade="all, delete-orphan",
        order_by="PipelineStage.position"
    )
    opportunities: Mapped[list["Opportunity"]] = relationship(  # noqa: F821
        back_populates="pipeline", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Pipeline {self.name!r}>"


class PipelineStage(UUIDMixin, TimestampMixin, GHLSyncMixin, Base):
    __tablename__ = "pipeline_stage"
    __table_args__ = (UniqueConstraint("pipeline_id", "name", name="uq_stage_pipeline_name"),)

    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("pipeline.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    position: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    pipeline: Mapped["Pipeline"] = relationship(back_populates="stages")
    opportunities: Mapped[list["Opportunity"]] = relationship(  # noqa: F821
        back_populates="stage"
    )

    def __repr__(self) -> str:
        return f"<PipelineStage {self.name!r}>"
