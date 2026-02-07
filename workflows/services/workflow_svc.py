"""Workflow CRUD service."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.workflow import Workflow, WorkflowStep


# ── Workflow CRUD ─────────────────────────────────────────────────────────

async def list_workflows(db: AsyncSession) -> list[Workflow]:
    stmt = (
        select(Workflow)
        .options(selectinload(Workflow.steps))
        .order_by(Workflow.updated_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


async def get_workflow(db: AsyncSession, workflow_id: uuid.UUID) -> Workflow | None:
    stmt = (
        select(Workflow)
        .where(Workflow.id == workflow_id)
        .options(selectinload(Workflow.steps), selectinload(Workflow.executions))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_workflow(
    db: AsyncSession,
    name: str,
    description: str | None = None,
    trigger_type: str | None = None,
    trigger_config: dict | None = None,
    ghl_location_id: str | None = None,
) -> Workflow:
    workflow = Workflow(
        name=name,
        description=description,
        trigger_type=trigger_type,
        trigger_config=trigger_config,
        ghl_location_id=ghl_location_id,
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return workflow


async def update_workflow(
    db: AsyncSession, workflow_id: uuid.UUID, **kwargs
) -> Workflow | None:
    workflow = await get_workflow(db, workflow_id)
    if not workflow:
        return None
    for key, value in kwargs.items():
        if hasattr(workflow, key):
            setattr(workflow, key, value)
    await db.commit()
    await db.refresh(workflow)
    return workflow


async def delete_workflow(db: AsyncSession, workflow_id: uuid.UUID) -> bool:
    stmt = select(Workflow).where(Workflow.id == workflow_id)
    result = await db.execute(stmt)
    workflow = result.scalar_one_or_none()
    if not workflow:
        return False
    await db.delete(workflow)
    await db.commit()
    return True


async def publish_workflow(db: AsyncSession, workflow_id: uuid.UUID) -> Workflow | None:
    return await update_workflow(db, workflow_id, status="published")


async def pause_workflow(db: AsyncSession, workflow_id: uuid.UUID) -> Workflow | None:
    return await update_workflow(db, workflow_id, status="paused")
