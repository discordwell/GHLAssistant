"""Task model."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDMixin, TimestampMixin, TenantMixin, GHLSyncMixin


class Task(UUIDMixin, TimestampMixin, TenantMixin, GHLSyncMixin, Base):
    __tablename__ = "task"

    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("contact.id", ondelete="SET NULL"),
        default=None, index=True
    )
    due_date: Mapped[date | None] = mapped_column(Date, default=None)
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending, in_progress, done
    priority: Mapped[int] = mapped_column(Integer, default=0)  # 0=normal, 1=high, 2=urgent
    assigned_to: Mapped[str | None] = mapped_column(String(100), default=None)

    # Relationships
    contact: Mapped["Contact | None"] = relationship(back_populates="tasks")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Task {self.title!r}>"
