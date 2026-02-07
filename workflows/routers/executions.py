"""Execution history routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..app import templates
from ..database import get_db
from ..models.execution import WorkflowExecution

router = APIRouter(prefix="/executions")


@router.get("/")
async def execution_list(request: Request, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(WorkflowExecution)
        .options(selectinload(WorkflowExecution.workflow))
        .order_by(WorkflowExecution.created_at.desc())
        .limit(50)
    )
    result = await db.execute(stmt)
    executions = list(result.scalars().all())
    return templates.TemplateResponse(
        "executions/list.html",
        {"request": request, "executions": executions},
    )


@router.get("/{execution_id}")
async def execution_detail(
    request: Request,
    execution_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(WorkflowExecution)
        .where(WorkflowExecution.id == execution_id)
        .options(
            selectinload(WorkflowExecution.workflow),
            selectinload(WorkflowExecution.step_executions),
        )
    )
    result = await db.execute(stmt)
    execution = result.scalar_one_or_none()
    if not execution:
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/executions", status_code=303)
    return templates.TemplateResponse(
        "executions/detail.html",
        {"request": request, "execution": execution},
    )
