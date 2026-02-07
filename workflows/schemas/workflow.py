"""Pydantic models for workflow API."""

from __future__ import annotations

from pydantic import BaseModel


class WorkflowCreate(BaseModel):
    name: str
    description: str | None = None
    trigger_type: str | None = None
    trigger_config: dict | None = None
    ghl_location_id: str | None = None


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    trigger_type: str | None = None
    trigger_config: dict | None = None


class StepCreate(BaseModel):
    step_type: str  # action/condition/delay
    action_type: str | None = None
    config: dict | None = None
    label: str | None = None
    canvas_x: float = 300.0
    canvas_y: float = 100.0


class StepUpdate(BaseModel):
    action_type: str | None = None
    config: dict | None = None
    label: str | None = None
    canvas_x: float | None = None
    canvas_y: float | None = None


class ConnectionCreate(BaseModel):
    from_step_id: str
    to_step_id: str
    connection_type: str = "next"  # next/true_branch/false_branch


class ConnectionDelete(BaseModel):
    from_step_id: str
    connection_type: str = "next"
