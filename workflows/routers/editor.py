"""Visual editor router — Drawflow canvas page."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..app import templates
from ..database import get_db
from ..services import workflow_svc

router = APIRouter(prefix="/workflows")


@router.get("/{workflow_id}/edit")
async def editor_page(
    request: Request,
    workflow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    workflow = await workflow_svc.get_workflow(db, workflow_id)
    if not workflow:
        return RedirectResponse("/", status_code=303)

    # Build step/connection data for Drawflow initialization
    steps_data = []
    connections = []
    for step in workflow.steps:
        steps_data.append({
            "id": str(step.id),
            "step_type": step.step_type,
            "action_type": step.action_type,
            "label": step.label or "",
            "config": step.config or {},
            "canvas_x": step.canvas_x,
            "canvas_y": step.canvas_y,
        })
        if step.next_step_id:
            connections.append({
                "from": str(step.id),
                "to": str(step.next_step_id),
                "type": "next",
            })
        if step.true_branch_step_id:
            connections.append({
                "from": str(step.id),
                "to": str(step.true_branch_step_id),
                "type": "true_branch",
            })
        if step.false_branch_step_id:
            connections.append({
                "from": str(step.id),
                "to": str(step.false_branch_step_id),
                "type": "false_branch",
            })

    return templates.TemplateResponse(
        "editor/canvas.html",
        {
            "request": request,
            "workflow": workflow,
            "steps_data": steps_data,
            "connections": connections,
        },
    )
