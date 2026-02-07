"""Conversation and Message models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, Boolean, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDMixin, TimestampMixin, TenantMixin, GHLSyncMixin


class Conversation(UUIDMixin, TimestampMixin, TenantMixin, GHLSyncMixin, Base):
    __tablename__ = "conversation"
    __table_args__ = (
        Index("ix_conversation_location_contact", "location_id", "contact_id"),
    )

    contact_id: Mapped["uuid.UUID | None"] = mapped_column(
        Uuid, ForeignKey("contact.id", ondelete="SET NULL"), default=None, index=True
    )
    subject: Mapped[str | None] = mapped_column(String(255), default=None)
    channel: Mapped[str] = mapped_column(String(20), default="sms")  # sms, email
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    unread_count: Mapped[int] = mapped_column(Integer, default=0)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    contact: Mapped["Contact | None"] = relationship(back_populates="conversations")  # noqa: F821
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan",
        order_by="Message.created_at.asc()",
    )


class Message(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "message"
    __table_args__ = (
        Index("ix_message_conversation", "conversation_id", "created_at"),
    )

    location_id: Mapped["uuid.UUID"] = mapped_column(
        Uuid, ForeignKey("location.id", ondelete="CASCADE"), index=True
    )
    conversation_id: Mapped["uuid.UUID"] = mapped_column(
        Uuid, ForeignKey("conversation.id", ondelete="CASCADE")
    )
    contact_id: Mapped["uuid.UUID | None"] = mapped_column(
        Uuid, ForeignKey("contact.id", ondelete="SET NULL"), default=None
    )
    direction: Mapped[str] = mapped_column(String(20))  # inbound, outbound
    channel: Mapped[str] = mapped_column(String(20))  # sms, email
    body: Mapped[str | None] = mapped_column(Text, default=None)
    subject: Mapped[str | None] = mapped_column(String(255), default=None)
    from_address: Mapped[str | None] = mapped_column(String(255), default=None)
    to_address: Mapped[str | None] = mapped_column(String(255), default=None)
    provider_id: Mapped[str | None] = mapped_column(String(200), default=None)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued/sent/delivered/failed/received
    status_detail: Mapped[str | None] = mapped_column(String(500), default=None)

    # Relationships
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
