"""Tests for contact and conversation pagination params."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from maxlevel.api.calendars import CalendarsAPI
from maxlevel.api.contacts import ContactsAPI
from maxlevel.api.conversations import ConversationsAPI


class DummyClient:
    """Minimal client stub that records outgoing API params."""

    def __init__(self, location_id: str = "loc_test"):
        self.config = SimpleNamespace(location_id=location_id)
        self.calls: list[tuple[str, dict]] = []

    async def _get(self, endpoint: str, **params):
        self.calls.append((endpoint, params))
        return {}


@pytest.mark.asyncio
async def test_contacts_list_ignores_offset_and_supports_start_after_cursor():
    client = DummyClient()
    api = ContactsAPI(client)

    await api.list(limit=200, offset=40)

    endpoint, params = client.calls[-1]
    assert endpoint == "/contacts/"
    assert params["locationId"] == "loc_test"
    assert params["limit"] == 100
    assert "offset" not in params

    await api.list(limit=5, start_after_id="contact_123", start_after=1770514874045)
    endpoint, params = client.calls[-1]
    assert endpoint == "/contacts/"
    assert params["startAfterId"] == "contact_123"
    assert params["startAfter"] == 1770514874045


@pytest.mark.asyncio
async def test_conversations_list_and_messages_support_offset():
    client = DummyClient()
    api = ConversationsAPI(client)

    await api.list(limit=60, offset=20)
    await api.messages("conv_123", limit=100, offset=80)

    list_endpoint, list_params = client.calls[-2]
    msg_endpoint, msg_params = client.calls[-1]

    assert list_endpoint == "/conversations/search"
    assert list_params["offset"] == 20
    assert list_params["limit"] == 60

    assert msg_endpoint == "/conversations/conv_123/messages"
    assert msg_params["offset"] == 80
    assert msg_params["limit"] == 100


@pytest.mark.asyncio
async def test_calendars_get_appointments_supports_offset_and_limit():
    client = DummyClient()
    api = CalendarsAPI(client)

    await api.get_appointments(calendar_id="cal_123", limit=250, offset=50)

    endpoint, params = client.calls[-1]
    assert endpoint == "/calendars/appointments"
    assert params["calendarId"] == "cal_123"
    assert params["limit"] == 100
    assert params["offset"] == 50
