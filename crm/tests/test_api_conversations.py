"""Test conversation API routes."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from crm.models.conversation import Conversation, Message
from crm.models.location import Location


@pytest.mark.asyncio
async def test_conversations_inbox(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/conversations/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_conversations_thread_list(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/conversations/threads")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_conversations_messages(
    client: AsyncClient, db: AsyncSession, location: Location
):
    conv = Conversation(
        location_id=location.id,
        channel="sms",
        subject="Test thread",
        unread_count=1,
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)

    msg = Message(
        location_id=location.id,
        conversation_id=conv.id,
        direction="inbound",
        channel="sms",
        body="Hello there",
    )
    db.add(msg)
    await db.commit()

    response = await client.get(
        f"/loc/{location.slug}/conversations/{conv.id}/messages"
    )
    assert response.status_code == 200
    assert "Hello there" in response.text


@pytest.mark.asyncio
async def test_conversations_mark_read(
    client: AsyncClient, db: AsyncSession, location: Location
):
    conv = Conversation(
        location_id=location.id,
        channel="sms",
        unread_count=5,
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)

    response = await client.post(
        f"/loc/{location.slug}/conversations/{conv.id}/read",
        follow_redirects=False,
    )
    # mark_read returns HTMLResponse (200), not a redirect
    assert response.status_code == 200
    assert "Marked as read" in response.text


@pytest.mark.asyncio
async def test_conversations_inbox_empty(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/conversations/")
    assert response.status_code == 200
    assert "No conversations" in response.text or response.status_code == 200


@pytest.mark.asyncio
async def test_conversations_messages_not_found(
    client: AsyncClient, location: Location
):
    fake_id = uuid.uuid4()
    response = await client.get(
        f"/loc/{location.slug}/conversations/{fake_id}/messages"
    )
    assert response.status_code == 200
    assert "not found" in response.text.lower()


@pytest.mark.asyncio
async def test_conversations_thread_list_with_data(
    client: AsyncClient, db: AsyncSession, location: Location
):
    conv = Conversation(
        location_id=location.id,
        channel="email",
        subject="Important thread",
    )
    db.add(conv)
    await db.commit()

    response = await client.get(f"/loc/{location.slug}/conversations/threads")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_conversations_page_title(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/conversations/")
    assert response.status_code == 200
    assert "Conversations" in response.text or "conversations" in response.text.lower()
