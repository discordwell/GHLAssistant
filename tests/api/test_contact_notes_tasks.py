"""Regression tests for contact Notes/Tasks endpoints.

Historically this code used /notes/ and /tasks/ endpoints which 404 on
backend.leadconnectorhq.com. Notes/Tasks are nested under the contact resource.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from maxlevel.api.contacts import ContactsAPI


class DummyClient:
    def __init__(self, *, location_id: str | None = "loc_test"):
        self.config = SimpleNamespace(location_id=location_id)
        self.get_calls: list[tuple[str, dict]] = []
        self.post_calls: list[tuple[str, dict | None]] = []

    async def _get(self, endpoint: str, **params):
        self.get_calls.append((endpoint, params))
        return {}

    async def _post(self, endpoint: str, data: dict | None = None):
        self.post_calls.append((endpoint, data))
        return {}


@pytest.mark.asyncio
async def test_get_notes_uses_contact_nested_endpoint_and_ignores_location_id():
    client = DummyClient()
    api = ContactsAPI(client)

    await api.get_notes("contact_123", location_id="loc_override")

    endpoint, params = client.get_calls[-1]
    assert endpoint == "/contacts/contact_123/notes"
    assert params == {}


@pytest.mark.asyncio
async def test_add_note_uses_contact_nested_endpoint_and_ignores_location_id():
    client = DummyClient()
    api = ContactsAPI(client)

    await api.add_note("contact_123", "hello", location_id="loc_override")

    endpoint, data = client.post_calls[-1]
    assert endpoint == "/contacts/contact_123/notes"
    assert data == {"body": "hello"}


@pytest.mark.asyncio
async def test_get_tasks_uses_contact_nested_endpoint_and_optionally_passes_location_id():
    client = DummyClient(location_id="loc_test")
    api = ContactsAPI(client)

    await api.get_tasks("contact_123")
    endpoint, params = client.get_calls[-1]
    assert endpoint == "/contacts/contact_123/tasks"
    assert params == {"locationId": "loc_test"}

    await api.get_tasks("contact_123", location_id="loc_override")
    endpoint, params = client.get_calls[-1]
    assert endpoint == "/contacts/contact_123/tasks"
    assert params == {"locationId": "loc_override"}


@pytest.mark.asyncio
async def test_add_task_requires_due_date_and_maps_description_to_body():
    client = DummyClient(location_id=None)
    api = ContactsAPI(client)

    with pytest.raises(ValueError):
        await api.add_task("contact_123", "Call back", due_date=None)

    await api.add_task(
        "contact_123",
        "Call back",
        due_date="2026-02-11",
        description="Details",
        completed=True,
        location_id="loc_override",
    )

    endpoint, data = client.post_calls[-1]
    assert endpoint == "/contacts/contact_123/tasks"
    assert data == {
        "title": "Call back",
        "dueDate": "2026-02-11",
        "completed": True,
        "body": "Details",
    }

