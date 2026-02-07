"""Note model - attached to contacts."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDMixin, TimestampMixin, TenantMixin, GHLSyncMixin


class Note(UUIDMixin, TimestampMixin, TenantMixin, GHLSyncMixin, Base):
    __tablename__ = "note"

    contact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("contact.id", ondelete="CASCADE"), index=True
    )
    body: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(100), default=None)

    # Relationships
    contact: Mapped["Contact"] = relationship(back_populates="notes")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Note contact={self.contact_id}>"
