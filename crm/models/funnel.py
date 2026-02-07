"""Funnel and FunnelPage models."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDMixin, TimestampMixin, TenantMixin, GHLSyncMixin


class Funnel(UUIDMixin, TimestampMixin, TenantMixin, GHLSyncMixin, Base):
    __tablename__ = "funnel"

    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    pages: Mapped[list["FunnelPage"]] = relationship(
        back_populates="funnel", cascade="all, delete-orphan",
        order_by="FunnelPage.position",
    )


class FunnelPage(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "funnel_page"
    __table_args__ = (
        UniqueConstraint("funnel_id", "url_slug", name="uq_funnel_page_slug"),
    )

    funnel_id: Mapped["uuid.UUID"] = mapped_column(
        Uuid, ForeignKey("funnel.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    url_slug: Mapped[str] = mapped_column(String(100))
    content_html: Mapped[str | None] = mapped_column(Text, default=None)
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    ghl_id: Mapped[str | None] = mapped_column(String(100), default=None)

    # Relationships
    funnel: Mapped["Funnel"] = relationship(back_populates="pages")
