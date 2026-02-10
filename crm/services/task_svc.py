"""Task service."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.task import Task


def _coerce_date(value: object) -> date | None:
    """Coerce common date representations into a Python `date`.

    Postgres expects a real date object for Date columns; strings that may
    "work" in SQLite will fail when bound by asyncpg.
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        # Preserve day in a stable timezone.
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        # Common HTML date input format: YYYY-MM-DD
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            pass
        # ISO datetime string.
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
        except ValueError:
            return None

    return None


async def list_tasks(
    db: AsyncSession,
    location_id: uuid.UUID,
    *,
    status: str | None = None,
    contact_id: uuid.UUID | None = None,
) -> list[Task]:
    stmt = select(Task).where(Task.location_id == location_id)
    if status:
        stmt = stmt.where(Task.status == status)
    if contact_id:
        stmt = stmt.where(Task.contact_id == contact_id)
    stmt = stmt.options(selectinload(Task.contact)).order_by(Task.due_date.asc().nullslast())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_task(db: AsyncSession, location_id: uuid.UUID, **kwargs) -> Task:
    if "due_date" in kwargs:
        kwargs["due_date"] = _coerce_date(kwargs.get("due_date"))
    task = Task(location_id=location_id, **kwargs)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def update_task(db: AsyncSession, task_id: uuid.UUID, **kwargs) -> Task | None:
    stmt = select(Task).where(Task.id == task_id)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        return None
    if "due_date" in kwargs:
        kwargs["due_date"] = _coerce_date(kwargs.get("due_date"))
    for key, value in kwargs.items():
        setattr(task, key, value)
    await db.commit()
    await db.refresh(task)
    return task


async def delete_task(db: AsyncSession, task_id: uuid.UUID) -> bool:
    stmt = select(Task).where(Task.id == task_id)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        return False
    await db.delete(task)
    await db.commit()
    return True
