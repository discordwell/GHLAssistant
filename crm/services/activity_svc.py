"""Activity service - audit trail logging."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.activity import Activity


async def log_activity(
    db: AsyncSession,
    location_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    action: str,
    description: str | None = None,
    metadata_json: dict | None = None,
    created_by: str | None = None,
) -> Activity:
    activity = Activity(
        location_id=location_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        description=description,
        metadata_json=metadata_json,
        created_by=created_by,
    )
    db.add(activity)
    await db.commit()
    await db.refresh(activity)
    return activity


async def list_activities(
    db: AsyncSession,
    location_id: uuid.UUID,
    *,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    limit: int = 50,
) -> list[Activity]:
    stmt = select(Activity).where(Activity.location_id == location_id)
    if entity_type:
        stmt = stmt.where(Activity.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(Activity.entity_id == entity_id)
    stmt = stmt.order_by(Activity.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())
