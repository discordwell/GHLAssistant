"""Campaign, CampaignStep, and CampaignEnrollment models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime, ForeignKey, Integer, String, Text, Uuid, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDMixin, TimestampMixin, TenantMixin, GHLSyncMixin


class Campaign(UUIDMixin, TimestampMixin, TenantMixin, GHLSyncMixin, Base):
    __tablename__ = "campaign"

    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft/active/paused/completed

    # Relationships
    steps: Mapped[list["CampaignStep"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan",
        order_by="CampaignStep.position",
    )
    enrollments: Mapped[list["CampaignEnrollment"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan",
    )


class CampaignStep(UUIDMixin, Base):
    __tablename__ = "campaign_step"

    campaign_id: Mapped["uuid.UUID"] = mapped_column(
        Uuid, ForeignKey("campaign.id", ondelete="CASCADE"), index=True
    )
    step_type: Mapped[str] = mapped_column(String(20))  # email, sms
    position: Mapped[int] = mapped_column(Integer, default=0)
    subject: Mapped[str | None] = mapped_column(String(255), default=None)
    body: Mapped[str | None] = mapped_column(Text, default=None)
    delay_minutes: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    campaign: Mapped["Campaign"] = relationship(back_populates="steps")


class CampaignEnrollment(UUIDMixin, Base):
    __tablename__ = "campaign_enrollment"
    __table_args__ = (
        UniqueConstraint("campaign_id", "contact_id", name="uq_campaign_enrollment"),
    )

    location_id: Mapped["uuid.UUID"] = mapped_column(
        Uuid, ForeignKey("location.id", ondelete="CASCADE"), index=True
    )
    campaign_id: Mapped["uuid.UUID"] = mapped_column(
        Uuid, ForeignKey("campaign.id", ondelete="CASCADE"), index=True
    )
    contact_id: Mapped["uuid.UUID"] = mapped_column(
        Uuid, ForeignKey("contact.id", ondelete="CASCADE"), index=True
    )
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active/completed/paused/failed
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    # Relationships
    campaign: Mapped["Campaign"] = relationship(back_populates="enrollments")
    contact: Mapped["Contact"] = relationship()  # noqa: F821
