"""Test conversation service."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from crm.models.contact import Contact
from crm.models.conversation import Conversation, Message
from crm.models.location import Location
from crm.services import conversation_svc


async def _make_contact(db: AsyncSession, location: Location) -> Contact:
    contact = Contact(location_id=location.id, first_name="Test", email="test@example.com")
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return contact


async def _make_conversation(
    db: AsyncSession,
    location: Location,
    contact: Contact | None = None,
    *,
    unread_count: int = 0,
    is_archived: bool = False,
    subject: str | None = None,
) -> Conversation:
    conv = Conversation(
        location_id=location.id,
        contact_id=contact.id if contact else None,
        subject=subject,
        channel="sms",
        unread_count=unread_count,
        is_archived=is_archived,
        last_message_at=datetime.now(timezone.utc),
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


async def _make_message(
    db: AsyncSession,
    location: Location,
    conversation: Conversation,
    body: str = "Hello",
    direction: str = "inbound",
) -> Message:
    msg = Message(
        location_id=location.id,
        conversation_id=conversation.id,
        direction=direction,
        channel="sms",
        body=body,
        status="delivered",
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg


@pytest.mark.asyncio
async def test_list_conversations_empty(db: AsyncSession, location: Location):
    convs, total = await conversation_svc.list_conversations(db, location.id)
    assert total == 0
    assert convs == []


@pytest.mark.asyncio
async def test_create_and_list_conversations(db: AsyncSession, location: Location):
    contact = await _make_contact(db, location)
    await _make_conversation(db, location, contact, subject="Chat 1")
    await _make_conversation(db, location, contact, subject="Chat 2")

    convs, total = await conversation_svc.list_conversations(db, location.id)
    assert total == 2
    assert len(convs) == 2


@pytest.mark.asyncio
async def test_get_conversation_with_messages(db: AsyncSession, location: Location):
    contact = await _make_contact(db, location)
    conv = await _make_conversation(db, location, contact)
    await _make_message(db, location, conv, body="Hi there")

    fetched = await conversation_svc.get_conversation(db, conv.id)
    assert fetched is not None
    assert fetched.id == conv.id
    assert len(fetched.messages) == 1
    assert fetched.messages[0].body == "Hi there"


@pytest.mark.asyncio
async def test_get_conversation_not_found(db: AsyncSession, location: Location):
    result = await conversation_svc.get_conversation(db, uuid.uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_get_messages(db: AsyncSession, location: Location):
    contact = await _make_contact(db, location)
    conv = await _make_conversation(db, location, contact)
    await _make_message(db, location, conv, body="Msg 1")
    await _make_message(db, location, conv, body="Msg 2")

    messages = await conversation_svc.get_messages(db, conv.id)
    assert len(messages) == 2
    assert messages[0].body == "Msg 1"
    assert messages[1].body == "Msg 2"


@pytest.mark.asyncio
async def test_mark_read(db: AsyncSession, location: Location):
    contact = await _make_contact(db, location)
    conv = await _make_conversation(db, location, contact, unread_count=3)
    assert conv.unread_count == 3

    await conversation_svc.mark_read(db, conv.id)

    fetched = await conversation_svc.get_conversation(db, conv.id)
    assert fetched is not None
    assert fetched.unread_count == 0


@pytest.mark.asyncio
async def test_archive_conversation(db: AsyncSession, location: Location):
    contact = await _make_contact(db, location)
    conv = await _make_conversation(db, location, contact)

    await conversation_svc.archive_conversation(db, conv.id)

    # Should not appear in default (non-archived) listing
    convs, total = await conversation_svc.list_conversations(db, location.id)
    ids = [c.id for c in convs]
    assert conv.id not in ids


@pytest.mark.asyncio
async def test_list_conversations_archived(db: AsyncSession, location: Location):
    contact = await _make_contact(db, location)
    await _make_conversation(db, location, contact, is_archived=True)
    await _make_conversation(db, location, contact, is_archived=False)

    archived, total = await conversation_svc.list_conversations(
        db, location.id, archived=True
    )
    assert total == 1
    assert archived[0].is_archived is True


@pytest.mark.asyncio
async def test_list_conversations_pagination(db: AsyncSession, location: Location):
    contact = await _make_contact(db, location)
    for i in range(5):
        await _make_conversation(db, location, contact, subject=f"Conv {i}")

    convs, total = await conversation_svc.list_conversations(
        db, location.id, offset=0, limit=2
    )
    assert total == 5
    assert len(convs) == 2

    convs2, total2 = await conversation_svc.list_conversations(
        db, location.id, offset=2, limit=2
    )
    assert total2 == 5
    assert len(convs2) == 2


@pytest.mark.asyncio
async def test_get_messages_empty(db: AsyncSession, location: Location):
    contact = await _make_contact(db, location)
    conv = await _make_conversation(db, location, contact)

    messages = await conversation_svc.get_messages(db, conv.id)
    assert messages == []
