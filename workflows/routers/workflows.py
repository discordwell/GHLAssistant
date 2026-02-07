"""Workflow CRUD routes (HTML form-based)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..app import templates
from ..database import get_db
from ..services import workflow_svc

router = APIRouter(prefix="/workflows")


@router.get("/new")
async def new_workflow_form(request: Request):
    return templates.TemplateResponse(
        "dashboard/new.html",
        {"request": request},
    )


@router.post("/new")
async def create_workflow(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    trigger_type: str = Form("manual"),
    db: AsyncSession = Depends(get_db),
):
    workflow = await workflow_svc.create_workflow(
        db,
        name=name,
        description=description or None,
        trigger_type=trigger_type,
    )
    return RedirectResponse(f"/workflows/{workflow.id}/edit", status_code=303)


@router.get("/{workflow_id}")
async def workflow_detail(
    request: Request,
    workflow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    workflow = await workflow_svc.get_workflow(db, workflow_id)
    if not workflow:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        "dashboard/detail.html",
        {"request": request, "workflow": workflow},
    )


@router.post("/{workflow_id}/publish")
async def publish_workflow(
    workflow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    await workflow_svc.publish_workflow(db, workflow_id)
    return RedirectResponse(f"/workflows/{workflow_id}", status_code=303)


@router.post("/{workflow_id}/pause")
async def pause_workflow(
    workflow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    await workflow_svc.pause_workflow(db, workflow_id)
    return RedirectResponse(f"/workflows/{workflow_id}", status_code=303)


@router.post("/{workflow_id}/delete")
async def delete_workflow(
    workflow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    await workflow_svc.delete_workflow(db, workflow_id)
    return RedirectResponse("/", status_code=303)


@router.post("/{workflow_id}/run")
async def run_workflow(
    workflow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger a workflow execution."""
    from ..engine.runner import WorkflowRunner

    runner = WorkflowRunner(db)
    execution = await runner.run(workflow_id)
    return RedirectResponse(f"/executions/{execution.id}", status_code=303)
