"""SQLModel table definitions for the hiring tool."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Position(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    department: str | None = None
    description: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    status: str = Field(default="open")  # open / paused / filled / closed
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Candidate(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    ghl_contact_id: str | None = None
    ghl_opportunity_id: str | None = None
    first_name: str
    last_name: str
    email: str | None = Field(default=None, index=True)
    phone: str | None = None
    position_id: int | None = Field(default=None, foreign_key="position.id")
    stage: str = Field(default="Applied")
    score: float | None = None
    source: str | None = None
    resume_text: str | None = None
    resume_url: str | None = None
    desired_salary: float | None = None
    available_start: Optional[date] = None
    applied_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="active")  # active / hired / rejected / withdrawn
    last_synced_at: datetime | None = None


class InterviewFeedback(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    candidate_id: int = Field(foreign_key="candidate.id")
    interviewer_name: str
    interview_type: str  # phone / technical / behavioral / panel
    interview_date: datetime = Field(default_factory=datetime.utcnow)
    rating: int  # 1-5
    strengths: str | None = None
    concerns: str | None = None
    recommendation: str  # strong_hire / hire / neutral / no_hire / strong_no_hire
    notes: str | None = None


class CandidateActivity(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    candidate_id: int = Field(foreign_key="candidate.id")
    activity_type: str  # stage_change / note / interview / score_update / synced / email
    description: str
    metadata_json: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str | None = None


class ScoringRubric(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    position_id: int = Field(foreign_key="position.id")
    criteria: str
    weight: float = 1.0
    max_points: int = 10


class CandidateScore(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    candidate_id: int = Field(foreign_key="candidate.id")
    rubric_id: int = Field(foreign_key="scoringrubric.id")
    points: int
    notes: str | None = None
