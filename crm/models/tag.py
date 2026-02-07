"""Tag model with M2M contact relationship."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDMixin, TimestampMixin, TenantMixin, GHLSyncMixin


class ContactTag(Base):
    """M2M join table for contacts <-> tags."""

    __tablename__ = "contact_tag"

    contact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("contact.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tag.id", ondelete="CASCADE"), primary_key=True
    )


class Tag(UUIDMixin, TimestampMixin, TenantMixin, GHLSyncMixin, Base):
    __tablename__ = "tag"
    __table_args__ = (UniqueConstraint("location_id", "name", name="uq_tag_location_name"),)

    name: Mapped[str] = mapped_column(String(100))

    # Relationships
    location: Mapped["Location"] = relationship(back_populates="tags")  # noqa: F821
    contacts: Mapped[list["Contact"]] = relationship(  # noqa: F821
        secondary="contact_tag", back_populates="tags"
    )

    def __repr__(self) -> str:
        return f"<Tag {self.name!r}>"
