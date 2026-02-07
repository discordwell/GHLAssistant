"""Activity model - polymorphic audit trail."""

from __future__ import annotations

import uuid

from sqlalchemy import JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UUIDMixin, TimestampMixin, TenantMixin


class Activity(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "activity"

    entity_type: Mapped[str] = mapped_column(String(50), index=True)  # contact, opportunity, etc.
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    action: Mapped[str] = mapped_column(String(50))  # created, updated, deleted, stage_change, etc.
    description: Mapped[str | None] = mapped_column(Text, default=None)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_by: Mapped[str | None] = mapped_column(String(100), default=None)

    def __repr__(self) -> str:
        return f"<Activity {self.action} {self.entity_type}>"
