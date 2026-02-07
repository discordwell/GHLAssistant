"""Survey, SurveyQuestion, and SurveySubmission models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDMixin, TimestampMixin, TenantMixin, GHLSyncMixin


class Survey(UUIDMixin, TimestampMixin, TenantMixin, GHLSyncMixin, Base):
    __tablename__ = "survey"

    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    questions: Mapped[list["SurveyQuestion"]] = relationship(
        back_populates="survey", cascade="all, delete-orphan",
        order_by="SurveyQuestion.position",
    )
    submissions: Mapped[list["SurveySubmission"]] = relationship(
        back_populates="survey", cascade="all, delete-orphan",
        order_by="SurveySubmission.submitted_at.desc()",
    )


class SurveyQuestion(UUIDMixin, Base):
    __tablename__ = "survey_question"

    survey_id: Mapped["uuid.UUID"] = mapped_column(
        Uuid, ForeignKey("survey.id", ondelete="CASCADE"), index=True
    )
    question_text: Mapped[str] = mapped_column(String(500))
    question_type: Mapped[str] = mapped_column(String(20), default="text")
    # text, rating, select, multi_select, yes_no, long_text
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    options_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    position: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    survey: Mapped["Survey"] = relationship(back_populates="questions")


class SurveySubmission(UUIDMixin, Base):
    __tablename__ = "survey_submission"

    location_id: Mapped["uuid.UUID"] = mapped_column(
        Uuid, ForeignKey("location.id", ondelete="CASCADE"), index=True
    )
    survey_id: Mapped["uuid.UUID"] = mapped_column(
        Uuid, ForeignKey("survey.id", ondelete="CASCADE"), index=True
    )
    contact_id: Mapped["uuid.UUID | None"] = mapped_column(
        Uuid, ForeignKey("contact.id", ondelete="SET NULL"), default=None
    )
    answers_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    # Relationships
    survey: Mapped["Survey"] = relationship(back_populates="submissions")
    contact: Mapped["Contact | None"] = relationship()  # noqa: F821
