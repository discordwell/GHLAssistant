"""Inbound webhook receiver for triggering workflows."""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..models.dispatch import WorkflowDispatch
from ..models.workflow import Workflow
from ..security import verify_webhook_request
from ..services.dispatch_svc import enqueue_dispatch, get_dispatch

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/{workflow_id}")
async def receive_webhook(
    workflow_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive a webhook and trigger the associated workflow."""
    raw_body = await request.body()
    verify_webhook_request(request, raw_body)

    # Parse incoming data
    content_type = request.headers.get("content-type", "").lower()
    trigger_data: dict = {}
    if "json" in content_type and raw_body:
        try:
            parsed = json.loads(raw_body.decode("utf-8"))
            if isinstance(parsed, dict):
                trigger_data = parsed
        except json.JSONDecodeError:
            raise HTTPException(status_code=422, detail="Invalid JSON body")
    elif raw_body:
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

    if settings.webhook_async_dispatch:
        dispatch = await enqueue_dispatch(db, workflow_id, trigger_data=trigger_data)
        return {
            "status": "accepted",
            "dispatch_id": str(dispatch.id),
            "dispatch_status": dispatch.status,
            "mode": "queued",
        }

    # Execute synchronously if async dispatch is disabled.
    from ..engine.runner import WorkflowRunner

    runner = WorkflowRunner(db)
    execution = await runner.run(workflow_id, trigger_data=trigger_data)
    return {
        "status": "accepted",
        "execution_id": str(execution.id),
        "result": execution.status,
        "steps_completed": execution.steps_completed,
        "mode": "sync",
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
        "auth": {
            "hmac_header": (
                "X-Webhook-Timestamp + X-Webhook-Signature"
                if settings.webhook_signing_secret
                else None
            ),
            "api_key_header": "X-API-Key" if settings.webhook_api_key else None,
        },
        "workflow": {
            "id": str(workflow.id),
            "name": workflow.name,
            "status": workflow.status,
        },
    }


@router.get("/dispatches/{dispatch_id}")
async def dispatch_status(
    dispatch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Fetch async webhook dispatch status."""
    dispatch: WorkflowDispatch | None = await get_dispatch(db, dispatch_id)
    if not dispatch:
        raise HTTPException(status_code=404, detail="Dispatch not found")

    return {
        "id": str(dispatch.id),
        "workflow_id": str(dispatch.workflow_id),
        "status": dispatch.status,
        "attempts": dispatch.attempts,
        "max_attempts": dispatch.max_attempts,
        "execution_id": str(dispatch.execution_id) if dispatch.execution_id else None,
        "error": dispatch.error_message,
    }
