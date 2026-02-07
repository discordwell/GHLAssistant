"""Custom field definitions (EAV pattern) and values."""

from __future__ import annotations

import uuid

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, Float, Boolean, Date, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UUIDMixin, TimestampMixin, TenantMixin, GHLSyncMixin


class CustomFieldDefinition(UUIDMixin, TimestampMixin, TenantMixin, GHLSyncMixin, Base):
    """Defines a custom field (works for contacts and opportunities)."""

    __tablename__ = "custom_field_definition"

    name: Mapped[str] = mapped_column(String(200))
    field_key: Mapped[str] = mapped_column(String(200), index=True)
    data_type: Mapped[str] = mapped_column(String(50))  # text, number, date, boolean, select
    entity_type: Mapped[str] = mapped_column(String(50), default="contact")  # contact, opportunity
    options_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    position: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self) -> str:
        return f"<CustomFieldDef {self.field_key!r}>"


class CustomFieldValue(UUIDMixin, TimestampMixin, Base):
    """Stores a custom field value for a specific entity (EAV pattern)."""

    __tablename__ = "custom_field_value"
    __table_args__ = (
        UniqueConstraint("definition_id", "entity_id", name="uq_cfv_def_entity"),
    )

    definition_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("custom_field_definition.id", ondelete="CASCADE"), index=True
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    entity_type: Mapped[str] = mapped_column(String(50))  # contact, opportunity

    value_text: Mapped[str | None] = mapped_column(Text, default=None)
    value_number: Mapped[float | None] = mapped_column(Float, default=None)
    value_date: Mapped[str | None] = mapped_column(String(50), default=None)
    value_bool: Mapped[bool | None] = mapped_column(Boolean, default=None)

    def __repr__(self) -> str:
        return f"<CustomFieldValue def={self.definition_id} entity={self.entity_id}>"
