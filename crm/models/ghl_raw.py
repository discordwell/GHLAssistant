"""Raw GHL payload preservation for loss-minimizing sync.

This table is intentionally generic so we can preserve fields we don't
explicitly model yet, while still allowing typed local columns for UI/indexing.
"""

from __future__ import annotations

from sqlalchemy import JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UUIDMixin, TimestampMixin, TenantMixin


class GHLRawEntity(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "ghl_raw_entity"
    __table_args__ = (
        UniqueConstraint("location_id", "entity_type", "ghl_id", name="uq_raw_location_type_id"),
    )

    entity_type: Mapped[str] = mapped_column(String(50), index=True)
    ghl_id: Mapped[str] = mapped_column(String(100), index=True)

    # For convenience/traceability (also stored on Location).
    ghl_location_id: Mapped[str | None] = mapped_column(String(100), default=None)

    payload_json: Mapped[dict] = mapped_column(JSON)
    source: Mapped[str | None] = mapped_column(String(50), default=None)  # api, browser, etc

