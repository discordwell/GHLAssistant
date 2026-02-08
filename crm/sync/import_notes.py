"""Import notes from GHL."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.contact import Contact
from ..models.location import Location
from ..models.note import Note
from ..schemas.sync import SyncResult
from .raw_store import upsert_raw_entity


def _extract_ghl_id(payload: dict) -> str:
    for key in ("id", "_id"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _extract_created_by(payload: dict) -> str | None:
    for key in ("createdBy", "createdByName", "createdById", "user", "userId"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


async def _resolve_contact_id(
    db: AsyncSession,
    *,
    location: Location,
    ghl_contact_id: str,
    contact_map: dict[str, uuid.UUID] | None,
) -> uuid.UUID | None:
    if contact_map and ghl_contact_id in contact_map:
        return contact_map[ghl_contact_id]
    stmt = select(Contact).where(
        Contact.location_id == location.id,
        Contact.ghl_id == ghl_contact_id,
    )
    contact = (await db.execute(stmt)).scalar_one_or_none()
    return contact.id if contact else None


async def import_notes(
    db: AsyncSession,
    location: Location,
    notes_by_contact: dict[str, list[dict]],
    contact_map: dict[str, uuid.UUID] | None = None,
) -> SyncResult:
    """Import notes grouped by GHL contact id."""
    result = SyncResult()
    now = datetime.now(timezone.utc)

    for ghl_contact_id, notes in (notes_by_contact or {}).items():
        if not isinstance(ghl_contact_id, str) or not ghl_contact_id:
            continue
        if not isinstance(notes, list) or not notes:
            continue

        local_contact_id = await _resolve_contact_id(
            db,
            location=location,
            ghl_contact_id=ghl_contact_id,
            contact_map=contact_map,
        )

        for note_payload in notes:
            if not isinstance(note_payload, dict):
                continue
            ghl_id = _extract_ghl_id(note_payload)
            if not ghl_id:
                continue

            await upsert_raw_entity(
                db,
                location=location,
                entity_type="note",
                ghl_id=ghl_id,
                payload=note_payload,
            )

            body = note_payload.get("body") or note_payload.get("content") or ""
            if not isinstance(body, str):
                body = str(body)

            stmt = select(Note).where(
                Note.location_id == location.id,
                Note.ghl_id == ghl_id,
            )
            note = (await db.execute(stmt)).scalar_one_or_none()

            if note:
                note.body = body
                note.created_by = _extract_created_by(note_payload)
                note.contact_id = local_contact_id or note.contact_id
                note.last_synced_at = now
                result.updated += 1
            else:
                if local_contact_id is None:
                    # Can't attach orphaned notes safely.
                    result.skipped += 1
                    continue
                note = Note(
                    location_id=location.id,
                    contact_id=local_contact_id,
                    body=body,
                    created_by=_extract_created_by(note_payload),
                    ghl_id=ghl_id,
                    ghl_location_id=location.ghl_location_id,
                    last_synced_at=now,
                )
                db.add(note)
                result.created += 1

    await db.commit()
    return result

