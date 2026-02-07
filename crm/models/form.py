"""Form, FormField, and FormSubmission models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDMixin, TimestampMixin, TenantMixin, GHLSyncMixin


class Form(UUIDMixin, TimestampMixin, TenantMixin, GHLSyncMixin, Base):
    __tablename__ = "form"

    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    fields: Mapped[list["FormField"]] = relationship(
        back_populates="form", cascade="all, delete-orphan",
        order_by="FormField.position",
    )
    submissions: Mapped[list["FormSubmission"]] = relationship(
        back_populates="form", cascade="all, delete-orphan",
        order_by="FormSubmission.submitted_at.desc()",
    )


class FormField(UUIDMixin, Base):
    __tablename__ = "form_field"

    form_id: Mapped["uuid.UUID"] = mapped_column(
        Uuid, ForeignKey("form.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(200))
    field_type: Mapped[str] = mapped_column(String(20), default="text")
    # text, email, phone, textarea, select, checkbox, number, date
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    options_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    position: Mapped[int] = mapped_column(Integer, default=0)
    placeholder: Mapped[str | None] = mapped_column(String(200), default=None)

    # Relationships
    form: Mapped["Form"] = relationship(back_populates="fields")


class FormSubmission(UUIDMixin, Base):
    __tablename__ = "form_submission"

    location_id: Mapped["uuid.UUID"] = mapped_column(
        Uuid, ForeignKey("location.id", ondelete="CASCADE"), index=True
    )
    form_id: Mapped["uuid.UUID"] = mapped_column(
        Uuid, ForeignKey("form.id", ondelete="CASCADE"), index=True
    )
    contact_id: Mapped["uuid.UUID | None"] = mapped_column(
        Uuid, ForeignKey("contact.id", ondelete="SET NULL"), default=None
    )
    data_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    source_ip: Mapped[str | None] = mapped_column(String(45), default=None)

    # Relationships
    form: Mapped["Form"] = relationship(back_populates="submissions")
    contact: Mapped["Contact | None"] = relationship()  # noqa: F821
