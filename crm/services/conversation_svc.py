"""Conversation service - CRUD + message threading."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.conversation import Conversation, Message


async def list_conversations(
    db: AsyncSession,
    location_id: uuid.UUID,
    *,
    archived: bool = False,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[Conversation], int]:
    stmt = (
        select(Conversation)
        .where(
            Conversation.location_id == location_id,
            Conversation.is_archived == archived,
        )
        .options(selectinload(Conversation.contact))
        .order_by(Conversation.last_message_at.desc().nullslast())
    )
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0
    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all()), total


async def get_conversation(
    db: AsyncSession, conversation_id: uuid.UUID
) -> Conversation | None:
    stmt = (
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .options(
            selectinload(Conversation.contact),
            selectinload(Conversation.messages),
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_messages(
    db: AsyncSession, conversation_id: uuid.UUID, limit: int = 100
) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def mark_read(db: AsyncSession, conversation_id: uuid.UUID) -> None:
    stmt = select(Conversation).where(Conversation.id == conversation_id)
    conv = (await db.execute(stmt)).scalar_one_or_none()
    if conv:
        conv.unread_count = 0
        await db.commit()


async def archive_conversation(db: AsyncSession, conversation_id: uuid.UUID) -> None:
    stmt = select(Conversation).where(Conversation.id == conversation_id)
    conv = (await db.execute(stmt)).scalar_one_or_none()
    if conv:
        conv.is_archived = True
        await db.commit()
