"""Inbound webhook receiver for triggering workflows."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.workflow import Workflow

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/{workflow_id}")
async def receive_webhook(
    workflow_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive a webhook and trigger the associated workflow."""
    # Parse incoming data
    content_type = request.headers.get("content-type", "")
    if "json" in content_type:
        trigger_data = await request.json()
    else:
        form = await request.form()
        trigger_data = dict(form)

    # Verify workflow exists and is published
    stmt = select(Workflow).where(Workflow.id == workflow_id)
    result = await db.execute(stmt)
    workflow = result.scalar_one_or_none()

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    if workflow.status != "published":
        raise HTTPException(status_code=422, detail="Workflow is not published")

    # Execute the workflow
    from ..engine.runner import WorkflowRunner

    runner = WorkflowRunner(db)
    execution = await runner.run(workflow_id, trigger_data=trigger_data)

    return {
        "status": "accepted",
        "execution_id": str(execution.id),
        "result": execution.status,
        "steps_completed": execution.steps_completed,
    }


@router.get("/{workflow_id}/test")
async def webhook_test_page(
    workflow_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Return webhook info for testing."""
    stmt = select(Workflow).where(Workflow.id == workflow_id)
    result = await db.execute(stmt)
    workflow = result.scalar_one_or_none()

    if not workflow:
        return {"error": "Workflow not found"}

    base_url = str(request.base_url).rstrip("/")
    return {
        "webhook_url": f"{base_url}/webhooks/{workflow_id}",
        "method": "POST",
        "content_type": "application/json",
        "workflow": {
            "id": str(workflow.id),
            "name": workflow.name,
            "status": workflow.status,
        },
    }
