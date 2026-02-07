"""Tag service."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.tag import Tag


async def list_tags(db: AsyncSession, location_id: uuid.UUID) -> list[Tag]:
    stmt = select(Tag).where(Tag.location_id == location_id).order_by(Tag.name)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_tag(db: AsyncSession, tag_id: uuid.UUID) -> Tag | None:
    stmt = select(Tag).where(Tag.id == tag_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_or_create_tag(
    db: AsyncSession, location_id: uuid.UUID, name: str
) -> tuple[Tag, bool]:
    """Get existing tag or create new one. Returns (tag, created)."""
    stmt = select(Tag).where(Tag.location_id == location_id, Tag.name == name)
    result = await db.execute(stmt)
    tag = result.scalar_one_or_none()
    if tag:
        return tag, False
    tag = Tag(location_id=location_id, name=name)
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return tag, True


async def create_tag(db: AsyncSession, location_id: uuid.UUID, name: str) -> Tag:
    tag = Tag(location_id=location_id, name=name)
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return tag


async def delete_tag(db: AsyncSession, tag_id: uuid.UUID) -> bool:
    tag = await get_tag(db, tag_id)
    if not tag:
        return False
    await db.delete(tag)
    await db.commit()
    return True
