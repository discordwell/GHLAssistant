"""Location model - the tenant root."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDMixin, TimestampMixin


class Location(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "location"

    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    ghl_location_id: Mapped[str | None] = mapped_column(String(100), default=None)
    ghl_company_id: Mapped[str | None] = mapped_column(String(100), default=None)

    # Relationships
    contacts: Mapped[list["Contact"]] = relationship(  # noqa: F821
        back_populates="location", cascade="all, delete-orphan"
    )
    tags: Mapped[list["Tag"]] = relationship(  # noqa: F821
        back_populates="location", cascade="all, delete-orphan"
    )
    pipelines: Mapped[list["Pipeline"]] = relationship(  # noqa: F821
        back_populates="location", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Location {self.slug!r}>"
