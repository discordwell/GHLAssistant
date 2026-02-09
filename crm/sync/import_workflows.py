"""Import workflows from GHL (raw preservation only).

GHL workflows are complex and (often) not fully CRUD-able via API.
For now we preserve the full raw workflow payload so we can rebuild/export later.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.location import Location
from ..schemas.sync import SyncResult
from .raw_store import upsert_raw_entity


def _extract_ghl_id(payload: dict) -> str:
    for key in ("id", "_id"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


async def import_workflows(
    db: AsyncSession,
    location: Location,
    workflows_data: list[dict],
    *,
    details_by_id: dict[str, dict] | None = None,
    source: str = "api",
) -> SyncResult:
    """Import workflows into raw storage.

    Args:
        workflows_data: List payload items from /workflows/
        details_by_id: Optional id -> detail payload (from /workflows/{id})
    """
    result = SyncResult()
    details_by_id = details_by_id or {}

    for summary in workflows_data:
        if not isinstance(summary, dict):
            continue
        ghl_id = _extract_ghl_id(summary)
        if not ghl_id:
            continue

        payload = details_by_id.get(ghl_id)
        if not isinstance(payload, dict):
            payload = summary

        created = await upsert_raw_entity(
            db,
            location=location,
            entity_type="workflow",
            ghl_id=ghl_id,
            payload=payload,
            source=source,
        )
        if created:
            result.created += 1
        else:
            result.updated += 1

    await db.commit()
    return result

