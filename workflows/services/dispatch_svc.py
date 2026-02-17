"""Dispatch queue service for durable webhook-triggered workflow execution."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models.dispatch import WorkflowDispatch


async def enqueue_dispatch(
    db: AsyncSession,
    workflow_id: uuid.UUID,
    trigger_data: dict | None,
    available_at: datetime | None = None,
) -> WorkflowDispatch:
    """Create and persist a workflow dispatch request."""
    dispatch = WorkflowDispatch(
        workflow_id=workflow_id,
        status="pending",
        trigger_data=trigger_data,
        available_at=available_at or datetime.now(timezone.utc),
        max_attempts=settings.dispatch_max_attempts,
    )
    db.add(dispatch)
    await db.commit()
    await db.refresh(dispatch)
    return dispatch


async def get_dispatch(db: AsyncSession, dispatch_id: uuid.UUID) -> WorkflowDispatch | None:
    """Fetch a dispatch item by ID."""
    result = await db.execute(select(WorkflowDispatch).where(WorkflowDispatch.id == dispatch_id))
    return result.scalar_one_or_none()


async def claim_next_dispatch(db: AsyncSession) -> WorkflowDispatch | None:
    """Claim the next runnable dispatch item.

    This uses a best-effort claim suitable for single-process workers and
    lightweight deployments.
    """
    now = datetime.now(timezone.utc)
    stmt = (
        select(WorkflowDispatch)
        .where(
            and_(
                WorkflowDispatch.status.in_(("pending", "retrying")),
                WorkflowDispatch.available_at <= now,
            )
        )
        .order_by(WorkflowDispatch.available_at.asc(), WorkflowDispatch.created_at.asc())
        .limit(1)
    )
    result = await db.execute(stmt)
    dispatch = result.scalar_one_or_none()
    if not dispatch:
        return None

    dispatch.status = "running"
    dispatch.started_at = now
    dispatch.error_message = None
    dispatch.attempts += 1
    await db.commit()
    await db.refresh(dispatch)
    return dispatch


async def mark_dispatch_completed(
    db: AsyncSession,
    dispatch: WorkflowDispatch,
    execution_id: uuid.UUID,
) -> None:
    """Mark a dispatch as completed."""
    dispatch.status = "completed"
    dispatch.execution_id = execution_id
    dispatch.finished_at = datetime.now(timezone.utc)
    await db.commit()


async def mark_dispatch_failed(
    db: AsyncSession,
    dispatch: WorkflowDispatch,
    error: str,
) -> None:
    """Mark dispatch failed or schedule retry with backoff."""
    now = datetime.now(timezone.utc)
    dispatch.error_message = error
    dispatch.finished_at = now

    if dispatch.attempts < dispatch.max_attempts:
        dispatch.status = "retrying"
        backoff = settings.dispatch_retry_backoff_seconds * dispatch.attempts
        dispatch.available_at = now + timedelta(seconds=backoff)
    else:
        dispatch.status = "failed"

    await db.commit()
