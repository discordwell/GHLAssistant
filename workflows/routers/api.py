"""JSON API for the visual editor (step and connection CRUD)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas.workflow import StepCreate, StepUpdate, ConnectionCreate, ConnectionDelete
from ..services import step_svc

router = APIRouter(prefix="/api")


@router.get("/workflows/{workflow_id}/steps")
async def list_steps(
    workflow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    steps = await step_svc.list_steps(db, workflow_id)
    return [
        {
            "id": str(s.id),
            "step_type": s.step_type,
            "action_type": s.action_type,
            "label": s.label,
            "config": s.config,
            "position": s.position,
            "canvas_x": s.canvas_x,
            "canvas_y": s.canvas_y,
            "next_step_id": str(s.next_step_id) if s.next_step_id else None,
            "true_branch_step_id": str(s.true_branch_step_id) if s.true_branch_step_id else None,
            "false_branch_step_id": str(s.false_branch_step_id) if s.false_branch_step_id else None,
        }
        for s in steps
    ]


@router.post("/workflows/{workflow_id}/steps")
async def create_step(
    workflow_id: uuid.UUID,
    data: StepCreate,
    db: AsyncSession = Depends(get_db),
):
    step = await step_svc.create_step(
        db,
        workflow_id=workflow_id,
        step_type=data.step_type,
        action_type=data.action_type,
        config=data.config,
        label=data.label,
        canvas_x=data.canvas_x,
        canvas_y=data.canvas_y,
    )
    return {
        "id": str(step.id),
        "step_type": step.step_type,
        "action_type": step.action_type,
        "label": step.label,
        "config": step.config,
        "position": step.position,
        "canvas_x": step.canvas_x,
        "canvas_y": step.canvas_y,
    }


@router.patch("/steps/{step_id}")
async def update_step(
    step_id: uuid.UUID,
    data: StepUpdate,
    db: AsyncSession = Depends(get_db),
):
    update_data = data.model_dump(exclude_unset=True)
    step = await step_svc.update_step(db, step_id, **update_data)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    return {
        "id": str(step.id),
        "step_type": step.step_type,
        "action_type": step.action_type,
        "label": step.label,
        "config": step.config,
        "canvas_x": step.canvas_x,
        "canvas_y": step.canvas_y,
    }


@router.delete("/steps/{step_id}")
async def delete_step(
    step_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    deleted = await step_svc.delete_step(db, step_id)
    return {"deleted": deleted}


@router.post("/connections")
async def create_connection(
    data: ConnectionCreate,
    db: AsyncSession = Depends(get_db),
):
    step = await step_svc.connect_steps(
        db,
        from_step_id=uuid.UUID(data.from_step_id),
        to_step_id=uuid.UUID(data.to_step_id),
        connection_type=data.connection_type,
    )
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    return {"connected": True}


@router.delete("/connections")
async def delete_connection(
    data: ConnectionDelete,
    db: AsyncSession = Depends(get_db),
):
    step = await step_svc.disconnect_steps(
        db,
        from_step_id=uuid.UUID(data.from_step_id),
        connection_type=data.connection_type,
    )
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    return {"disconnected": True}
