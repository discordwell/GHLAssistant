"""Tests for GHL Conversations routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from crm.models.location import Location


@pytest.mark.asyncio
async def test_inbox_no_ghl_location(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/conversations/")
    assert response.status_code == 200
    assert "GHL" in response.text or "No GHL" in response.text


@pytest.mark.asyncio
async def test_inbox_ghl_linked(client: AsyncClient, location: Location, db):
    location.ghl_location_id = "ghl_loc_123"
    await db.commit()

    mock_data = {"conversations": [
        {"id": "conv1", "contactName": "John Doe", "lastMessageBody": "Hello", "unreadCount": 2},
    ]}
    with patch("crm.routers.conversations.fetch_conversations", new_callable=AsyncMock, return_value=mock_data):
        response = await client.get(f"/loc/{location.slug}/conversations/")
    assert response.status_code == 200
    assert "John Doe" in response.text


@pytest.mark.asyncio
async def test_inbox_api_error(client: AsyncClient, location: Location, db):
    location.ghl_location_id = "ghl_loc_123"
    await db.commit()

    with patch("crm.routers.conversations.fetch_conversations", new_callable=AsyncMock, side_effect=Exception("err")):
        response = await client.get(f"/loc/{location.slug}/conversations/")
    assert response.status_code == 200
    assert "Failed" in response.text


@pytest.mark.asyncio
async def test_thread_list(client: AsyncClient, location: Location, db):
    location.ghl_location_id = "ghl_loc_123"
    await db.commit()

    mock_data = {"conversations": [{"id": "conv1", "contactName": "Jane"}]}
    with patch("crm.routers.conversations.fetch_conversations", new_callable=AsyncMock, return_value=mock_data):
        response = await client.get(f"/loc/{location.slug}/conversations/threads")
    assert response.status_code == 200
    assert "Jane" in response.text


@pytest.mark.asyncio
async def test_messages(client: AsyncClient, location: Location, db):
    location.ghl_location_id = "ghl_loc_123"
    await db.commit()

    mock_msgs = {"messages": [
        {"body": "Hi there", "direction": "inbound", "contactId": "c1", "type": "SMS", "dateAdded": "2025-01-01T00:00"},
    ]}
    with patch("crm.routers.conversations.fetch_conversation_messages", new_callable=AsyncMock, return_value=mock_msgs), \
         patch("crm.routers.conversations.mark_conversation_read", new_callable=AsyncMock):
        response = await client.get(f"/loc/{location.slug}/conversations/conv1/messages")
    assert response.status_code == 200
    assert "Hi there" in response.text


@pytest.mark.asyncio
async def test_messages_api_error(client: AsyncClient, location: Location, db):
    location.ghl_location_id = "ghl_loc_123"
    await db.commit()

    with patch("crm.routers.conversations.fetch_conversation_messages", new_callable=AsyncMock, side_effect=Exception("err")):
        response = await client.get(f"/loc/{location.slug}/conversations/conv1/messages")
    assert response.status_code == 200
    assert "err" in response.text


@pytest.mark.asyncio
async def test_send_sms(client: AsyncClient, location: Location, db):
    location.ghl_location_id = "ghl_loc_123"
    await db.commit()

    with patch("crm.routers.conversations.send_sms", new_callable=AsyncMock, return_value={"messageId": "m1"}):
        response = await client.post(
            f"/loc/{location.slug}/conversations/c1/sms",
            data={"message": "Hello!"},
        )
    assert response.status_code == 200
    assert "sent" in response.text.lower()


@pytest.mark.asyncio
async def test_send_sms_empty(client: AsyncClient, location: Location, db):
    location.ghl_location_id = "ghl_loc_123"
    await db.commit()

    response = await client.post(
        f"/loc/{location.slug}/conversations/c1/sms",
        data={"message": ""},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_send_email(client: AsyncClient, location: Location, db):
    location.ghl_location_id = "ghl_loc_123"
    await db.commit()

    with patch("crm.routers.conversations.send_email", new_callable=AsyncMock, return_value={"messageId": "m2"}):
        response = await client.post(
            f"/loc/{location.slug}/conversations/c1/email",
            data={"subject": "Test", "body": "Hello"},
        )
    assert response.status_code == 200
    assert "sent" in response.text.lower()


@pytest.mark.asyncio
async def test_send_email_missing_fields(client: AsyncClient, location: Location, db):
    location.ghl_location_id = "ghl_loc_123"
    await db.commit()

    response = await client.post(
        f"/loc/{location.slug}/conversations/c1/email",
        data={"subject": "", "body": ""},
    )
    assert response.status_code == 422
