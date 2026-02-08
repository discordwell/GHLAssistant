"""Regression tests for conversation export idempotency."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from crm.models.base import Base
from crm.models.contact import Contact
from crm.models.conversation import Conversation, Message
from crm.models.location import Location
from crm.sync.export_conversations import export_conversations


class FakeConversationsAPI:
    def __init__(self):
        self.sms_calls: list[tuple[str, str, str | None]] = []

    async def send_sms(self, contact_id: str, message: str, location_id: str | None = None):
        self.sms_calls.append((contact_id, message, location_id))
        return {"message": {"id": "ghl_msg_123"}}


class FakeGHL:
    def __init__(self):
        self.conversations = FakeConversationsAPI()


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_export_conversations_sets_provider_id_and_prevents_duplicate_send(db: AsyncSession):
    location = Location(
        id=uuid.uuid4(),
        name="Test Location",
        slug="test-location",
        timezone="UTC",
        ghl_location_id="ghl_loc_123",
    )
    db.add(location)
    await db.flush()

    contact = Contact(
        location_id=location.id,
        first_name="Test",
        email="test@example.com",
        ghl_id="ghl_contact_123",
    )
    db.add(contact)
    await db.flush()

    conv = Conversation(
        location_id=location.id,
        contact_id=contact.id,
        channel="sms",
        ghl_id="ghl_conv_123",
    )
    db.add(conv)
    await db.flush()

    msg = Message(
        location_id=location.id,
        conversation_id=conv.id,
        contact_id=contact.id,
        direction="outbound",
        channel="sms",
        body="Hello world",
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)

    ghl = FakeGHL()
    first = await export_conversations(db, location, ghl)
    await db.refresh(msg)

    assert first.created == 1
    assert first.errors == []
    assert msg.status == "sent"
    assert msg.provider_id == "ghl_msg_123"
    assert len(ghl.conversations.sms_calls) == 1

    second = await export_conversations(db, location, ghl)

    assert second.created == 0
    assert second.errors == []
    assert len(ghl.conversations.sms_calls) == 1
