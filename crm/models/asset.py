"""Canonical asset storage models.

Foundation primitive:
  Asset = immutable bytes (deduped by sha256) + metadata.

Everything else references an Asset via AssetRef or AssetRemoteMap.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDMixin, TimestampMixin, TenantMixin


class Asset(UUIDMixin, TimestampMixin, TenantMixin, Base):
    """Immutable bytes + metadata, deduped by sha256 per tenant location."""

    __tablename__ = "asset"
    __table_args__ = (
        UniqueConstraint("location_id", "sha256", name="uq_asset_location_sha256"),
        Index("ix_asset_location_sha256", "location_id", "sha256"),
    )

    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)

    content_type: Mapped[str | None] = mapped_column(String(200), default=None)
    original_filename: Mapped[str | None] = mapped_column(String(500), default=None)
    original_url: Mapped[str | None] = mapped_column(Text, default=None)
    source: Mapped[str | None] = mapped_column(String(50), default=None)

    # "Last seen" is updated by discovery/import runs (separate from updated_at
    # which is used for DB-level updates).
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    meta_json: Mapped[dict | None] = mapped_column(JSON, default=None)


class AssetRef(UUIDMixin, TimestampMixin, TenantMixin, Base):
    """Where an asset is referenced (entity + field path + original URL)."""

    __tablename__ = "asset_ref"
    __table_args__ = (
        # Use a fixed-size identity hash to avoid indexing large TEXT payloads
        # (signed URLs, data: URIs) which can break Postgres btree indexes.
        UniqueConstraint(
            "location_id",
            "identity_sha256",
            name="uq_asset_ref_location_identity_sha256",
        ),
        Index("ix_asset_ref_location_entity", "location_id", "entity_type"),
        Index("ix_asset_ref_location_identity_sha256", "location_id", "identity_sha256"),
    )

    identity_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("asset.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        default=None,
    )

    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True, default=None)
    remote_entity_id: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True, default=None)

    # JSON pointer or dotted path (best-effort; not interpreted by DB).
    field_path: Mapped[str | None] = mapped_column(String(500), default=None)

    # inline_image/attachment/background/etc (best-effort; not enforced).
    usage: Mapped[str | None] = mapped_column(String(50), default=None)

    # Exact URL as found in entity content (signed URLs included).
    original_url: Mapped[str | None] = mapped_column(Text, default=None)

    # Updated by discovery/import runs.
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    meta_json: Mapped[dict | None] = mapped_column(JSON, default=None)

    asset: Mapped[Asset | None] = relationship("Asset", lazy="joined")


class AssetRemoteMap(UUIDMixin, TimestampMixin, Base):
    """Mapping for export/import bijection (local Asset -> remote asset/url)."""

    __tablename__ = "asset_remote_map"
    __table_args__ = (
        UniqueConstraint(
            "asset_id",
            "target_system",
            "target_location_id",
            name="uq_asset_remote_map_asset_target",
        ),
        Index("ix_asset_remote_map_asset", "asset_id"),
    )

    asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("asset.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_system: Mapped[str] = mapped_column(String(50), nullable=False, default="ghl")
    target_location_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("location.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    remote_id: Mapped[str | None] = mapped_column(String(200), default=None)
    remote_url: Mapped[str | None] = mapped_column(Text, default=None)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    meta_json: Mapped[dict | None] = mapped_column(JSON, default=None)


class AssetJob(UUIDMixin, TimestampMixin, TenantMixin, Base):
    """Download/upload job queue for assets with retries."""

    __tablename__ = "asset_job"
    __table_args__ = (
        # Same idea as AssetRef: avoid indexing long TEXT URLs directly.
        UniqueConstraint(
            "location_id",
            "job_type",
            "url_sha256",
            name="uq_asset_job_location_type_url_sha256",
        ),
        Index("ix_asset_job_status_next", "status", "next_attempt_at"),
    )

    job_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # download/upload
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)

    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    asset_ref_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("asset_ref.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        default=None,
    )
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("asset.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        default=None,
    )

    url_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    url: Mapped[str | None] = mapped_column(Text, default=None)

    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)

    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    locked_by: Mapped[str | None] = mapped_column(String(200), default=None)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    last_error: Mapped[str | None] = mapped_column(Text, default=None)
    meta_json: Mapped[dict | None] = mapped_column(JSON, default=None)
