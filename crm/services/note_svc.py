"""Note service."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.note import Note


async def list_notes(
    db: AsyncSession, contact_id: uuid.UUID
) -> list[Note]:
    stmt = (
        select(Note)
        .where(Note.contact_id == contact_id)
        .order_by(Note.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_note(
    db: AsyncSession,
    location_id: uuid.UUID,
    contact_id: uuid.UUID,
    body: str,
    created_by: str | None = None,
) -> Note:
    note = Note(
        location_id=location_id,
        contact_id=contact_id,
        body=body,
        created_by=created_by,
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note


async def delete_note(db: AsyncSession, note_id: uuid.UUID) -> bool:
    stmt = select(Note).where(Note.id == note_id)
    result = await db.execute(stmt)
    note = result.scalar_one_or_none()
    if not note:
        return False
    await db.delete(note)
    await db.commit()
    return True
