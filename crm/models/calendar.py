"""Calendar, AvailabilityWindow, and Appointment models."""

from __future__ import annotations

import uuid
from datetime import datetime, time

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, Integer, String, Text, Time, Uuid, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDMixin, TimestampMixin, TenantMixin, GHLSyncMixin


class Calendar(UUIDMixin, TimestampMixin, TenantMixin, GHLSyncMixin, Base):
    __tablename__ = "calendar"

    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    timezone: Mapped[str] = mapped_column(String(50), default="America/New_York")
    slot_duration: Mapped[int] = mapped_column(Integer, default=30)  # minutes
    buffer_before: Mapped[int] = mapped_column(Integer, default=0)
    buffer_after: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    availability_windows: Mapped[list["AvailabilityWindow"]] = relationship(
        back_populates="calendar", cascade="all, delete-orphan",
        order_by="AvailabilityWindow.day_of_week, AvailabilityWindow.start_time",
    )
    appointments: Mapped[list["Appointment"]] = relationship(
        back_populates="calendar", cascade="all, delete-orphan",
        order_by="Appointment.start_time.desc()",
    )


class AvailabilityWindow(UUIDMixin, Base):
    __tablename__ = "availability_window"
    __table_args__ = (
        UniqueConstraint("calendar_id", "day_of_week", "start_time",
                         name="uq_availability_window"),
    )

    calendar_id: Mapped["uuid.UUID"] = mapped_column(
        Uuid, ForeignKey("calendar.id", ondelete="CASCADE"), index=True
    )
    day_of_week: Mapped[int] = mapped_column(Integer)  # 0=Mon, 6=Sun
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)

    # Relationships
    calendar: Mapped["Calendar"] = relationship(back_populates="availability_windows")


class Appointment(UUIDMixin, TimestampMixin, TenantMixin, GHLSyncMixin, Base):
    __tablename__ = "appointment"
    __table_args__ = (
        Index("ix_appointment_calendar_time", "calendar_id", "start_time"),
    )

    calendar_id: Mapped["uuid.UUID"] = mapped_column(
        Uuid, ForeignKey("calendar.id", ondelete="CASCADE"), index=True
    )
    contact_id: Mapped["uuid.UUID | None"] = mapped_column(
        Uuid, ForeignKey("contact.id", ondelete="SET NULL"), default=None
    )
    title: Mapped[str | None] = mapped_column(String(200), default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="confirmed")  # confirmed/cancelled/completed/no_show

    # Relationships
    calendar: Mapped["Calendar"] = relationship(back_populates="appointments")
    contact: Mapped["Contact | None"] = relationship()  # noqa: F821
