"""Base model classes and mixins for CRM models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UUIDMixin:
    """Adds a UUID primary key."""

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )


class TimestampMixin:
    """Adds created_at / updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TenantMixin:
    """Adds location_id FK for multi-tenant isolation."""

    location_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("location.id", ondelete="CASCADE"),
        index=True,
    )


class GHLSyncMixin:
    """Adds GHL sync tracking columns."""

    ghl_id: Mapped[str | None] = mapped_column(String(100), default=None, index=True)
    ghl_location_id: Mapped[str | None] = mapped_column(String(100), default=None)
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
