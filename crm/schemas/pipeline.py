"""Pipeline and opportunity schemas."""

from __future__ import annotations

import uuid
from pydantic import BaseModel


class PipelineCreate(BaseModel):
    name: str
    description: str | None = None


class StageCreate(BaseModel):
    name: str
    position: int = 0


class OpportunityCreate(BaseModel):
    name: str
    pipeline_id: uuid.UUID
    stage_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None
    monetary_value: float | None = None
    status: str = "open"
    source: str | None = None


class OpportunityUpdate(BaseModel):
    name: str | None = None
    stage_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None
    monetary_value: float | None = None
    status: str | None = None
    source: str | None = None
