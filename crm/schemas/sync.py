"""GHL sync schemas."""

from __future__ import annotations

from pydantic import BaseModel


class ImportPreview(BaseModel):
    tags: int = 0
    custom_fields: int = 0
    custom_values: int = 0
    pipelines: int = 0
    contacts: int = 0
    opportunities: int = 0
    notes: int = 0
    tasks: int = 0
    conversations: int = 0
    calendars: int = 0
    forms: int = 0
    surveys: int = 0
    campaigns: int = 0
    funnels: int = 0


class SyncResult(BaseModel):
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = []
