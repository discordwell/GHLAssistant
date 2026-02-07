"""Custom values - location-level template variables."""

from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UUIDMixin, TimestampMixin, TenantMixin, GHLSyncMixin


class CustomValue(UUIDMixin, TimestampMixin, TenantMixin, GHLSyncMixin, Base):
    __tablename__ = "custom_value"

    name: Mapped[str] = mapped_column(String(200))
    value: Mapped[str | None] = mapped_column(Text, default=None)

    def __repr__(self) -> str:
        return f"<CustomValue {self.name!r}>"
