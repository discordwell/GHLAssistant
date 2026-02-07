"""Contact model."""

from __future__ import annotations

from sqlalchemy import Index, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDMixin, TimestampMixin, TenantMixin, GHLSyncMixin


class Contact(UUIDMixin, TimestampMixin, TenantMixin, GHLSyncMixin, Base):
    __tablename__ = "contact"
    __table_args__ = (
        Index("ix_contact_location_email", "location_id", "email"),
    )

    first_name: Mapped[str | None] = mapped_column(String(100), default=None)
    last_name: Mapped[str | None] = mapped_column(String(100), default=None)
    email: Mapped[str | None] = mapped_column(String(255), default=None, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), default=None)
    company_name: Mapped[str | None] = mapped_column(String(200), default=None)
    address1: Mapped[str | None] = mapped_column(String(255), default=None)
    city: Mapped[str | None] = mapped_column(String(100), default=None)
    state: Mapped[str | None] = mapped_column(String(50), default=None)
    postal_code: Mapped[str | None] = mapped_column(String(20), default=None)
    country: Mapped[str | None] = mapped_column(String(50), default=None)
    source: Mapped[str | None] = mapped_column(String(100), default=None)
    dnd: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    location: Mapped["Location"] = relationship(back_populates="contacts")  # noqa: F821
    tags: Mapped[list["Tag"]] = relationship(  # noqa: F821
        secondary="contact_tag", back_populates="contacts"
    )
    notes: Mapped[list["Note"]] = relationship(  # noqa: F821
        back_populates="contact", cascade="all, delete-orphan"
    )
    tasks: Mapped[list["Task"]] = relationship(  # noqa: F821
        back_populates="contact", cascade="all, delete-orphan"
    )
    opportunities: Mapped[list["Opportunity"]] = relationship(  # noqa: F821
        back_populates="contact", cascade="all, delete-orphan"
    )

    @property
    def full_name(self) -> str:
        parts = [p for p in (self.first_name, self.last_name) if p]
        return " ".join(parts) or "Unnamed"

    def __repr__(self) -> str:
        return f"<Contact {self.full_name!r}>"
