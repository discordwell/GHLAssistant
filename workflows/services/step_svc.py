"""Workflow step management service."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.workflow import WorkflowStep


async def list_steps(db: AsyncSession, workflow_id: uuid.UUID) -> list[WorkflowStep]:
    stmt = (
        select(WorkflowStep)
        .where(WorkflowStep.workflow_id == workflow_id)
        .order_by(WorkflowStep.position)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_step(db: AsyncSession, step_id: uuid.UUID) -> WorkflowStep | None:
    stmt = select(WorkflowStep).where(WorkflowStep.id == step_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_step(
    db: AsyncSession,
    workflow_id: uuid.UUID,
    step_type: str,
    action_type: str | None = None,
    config: dict | None = None,
    label: str | None = None,
    position: int | None = None,
    canvas_x: float = 300.0,
    canvas_y: float = 100.0,
) -> WorkflowStep:
    if position is None:
        stmt = select(func.max(WorkflowStep.position)).where(
            WorkflowStep.workflow_id == workflow_id
        )
        result = await db.execute(stmt)
        max_pos = result.scalar()
        position = (max_pos + 1) if max_pos is not None else 0

    step = WorkflowStep(
        workflow_id=workflow_id,
        step_type=step_type,
        action_type=action_type,
        config=config,
        label=label or _default_label(step_type, action_type),
        position=position,
        canvas_x=canvas_x,
        canvas_y=canvas_y,
    )
    db.add(step)
    await db.commit()
    await db.refresh(step)
    return step


async def update_step(
    db: AsyncSession, step_id: uuid.UUID, **kwargs
) -> WorkflowStep | None:
    step = await get_step(db, step_id)
    if not step:
        return None
    for key, value in kwargs.items():
        if hasattr(step, key):
            setattr(step, key, value)
    await db.commit()
    await db.refresh(step)
    return step


async def delete_step(db: AsyncSession, step_id: uuid.UUID) -> bool:
    step = await get_step(db, step_id)
    if not step:
        return False
    await db.delete(step)
    await db.commit()
    return True


async def connect_steps(
    db: AsyncSession,
    from_step_id: uuid.UUID,
    to_step_id: uuid.UUID,
    connection_type: str = "next",
) -> WorkflowStep | None:
    """Connect two steps. connection_type: next, true_branch, false_branch."""
    step = await get_step(db, from_step_id)
    if not step:
        return None

    field_map = {
        "next": "next_step_id",
        "true_branch": "true_branch_step_id",
        "false_branch": "false_branch_step_id",
    }
    field = field_map.get(connection_type, "next_step_id")
    setattr(step, field, to_step_id)
    await db.commit()
    await db.refresh(step)
    return step


async def disconnect_steps(
    db: AsyncSession,
    from_step_id: uuid.UUID,
    connection_type: str = "next",
) -> WorkflowStep | None:
    """Remove a connection from a step."""
    step = await get_step(db, from_step_id)
    if not step:
        return None

    field_map = {
        "next": "next_step_id",
        "true_branch": "true_branch_step_id",
        "false_branch": "false_branch_step_id",
    }
    field = field_map.get(connection_type, "next_step_id")
    setattr(step, field, None)
    await db.commit()
    await db.refresh(step)
    return step


def _default_label(step_type: str, action_type: str | None) -> str:
    """Generate a default label for a step."""
    if step_type == "condition":
        return "If/Else"
    if step_type == "delay":
        return "Wait"
    if action_type:
        return action_type.replace("_", " ").title()
    return step_type.title()
