"""Raw entity payload upsert helpers for loss-minimizing sync."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.ghl_raw import GHLRawEntity
from ..models.location import Location


async def upsert_raw_entity(
    db: AsyncSession,
    *,
    location: Location,
    entity_type: str,
    ghl_id: str | None,
    payload: Any,
    source: str = "api",
) -> None:
    """Best-effort upsert for raw JSON payloads.

    No commit is performed here; callers batch commits.
    """
    if not isinstance(ghl_id, str) or not ghl_id:
        return
    if not isinstance(entity_type, str) or not entity_type:
        return
    if not isinstance(payload, dict):
        return

    stmt = select(GHLRawEntity).where(
        GHLRawEntity.location_id == location.id,
        GHLRawEntity.entity_type == entity_type,
        GHLRawEntity.ghl_id == ghl_id,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()

    if existing:
        existing.payload_json = payload
        existing.ghl_location_id = location.ghl_location_id
        existing.source = source
        return

    db.add(
        GHLRawEntity(
            location_id=location.id,
            entity_type=entity_type,
            ghl_id=ghl_id,
            ghl_location_id=location.ghl_location_id,
            payload_json=payload,
            source=source,
        )
    )

