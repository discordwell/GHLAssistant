"""Tests for GHL Calendars routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from crm.models.location import Location


@pytest.mark.asyncio
async def test_calendars_page_no_ghl_location(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/calendars/")
    assert response.status_code == 200
    assert "GHL" in response.text or "No GHL" in response.text


@pytest.mark.asyncio
async def test_calendars_page_ghl_linked(client: AsyncClient, location: Location, db):
    location.ghl_location_id = "ghl_loc_123"
    await db.commit()

    mock_data = {"calendars": [{"id": "cal1", "name": "Main Calendar", "eventType": "round_robin"}]}
    with patch("crm.routers.calendars.fetch_calendars", new_callable=AsyncMock, return_value=mock_data):
        response = await client.get(f"/loc/{location.slug}/calendars/")
    assert response.status_code == 200
    assert "Main Calendar" in response.text


@pytest.mark.asyncio
async def test_calendars_page_api_error(client: AsyncClient, location: Location, db):
    location.ghl_location_id = "ghl_loc_123"
    await db.commit()

    with patch("crm.routers.calendars.fetch_calendars", new_callable=AsyncMock, side_effect=Exception("timeout")):
        response = await client.get(f"/loc/{location.slug}/calendars/")
    assert response.status_code == 200
    assert "Failed" in response.text


@pytest.mark.asyncio
async def test_calendar_slots(client: AsyncClient, location: Location, db):
    location.ghl_location_id = "ghl_loc_123"
    await db.commit()

    mock_data = {"slots": {"2025-01-15": ["10:00", "11:00", "14:00"]}}
    with patch("crm.routers.calendars.fetch_calendar_slots", new_callable=AsyncMock, return_value=mock_data):
        response = await client.get(
            f"/loc/{location.slug}/calendars/cal1/slots?start=2025-01-15&end=2025-01-15"
        )
    assert response.status_code == 200
    assert "10:00" in response.text


@pytest.mark.asyncio
async def test_calendar_slots_no_start_date(client: AsyncClient, location: Location, db):
    location.ghl_location_id = "ghl_loc_123"
    await db.commit()

    response = await client.get(f"/loc/{location.slug}/calendars/cal1/slots")
    assert response.status_code == 200
    assert "required" in response.text.lower() or "Start date" in response.text


@pytest.mark.asyncio
async def test_book_appointment(client: AsyncClient, location: Location, db):
    location.ghl_location_id = "ghl_loc_123"
    await db.commit()

    with patch("crm.routers.calendars.book_appointment", new_callable=AsyncMock, return_value={"id": "apt1"}):
        response = await client.post(
            f"/loc/{location.slug}/calendars/cal1/book",
            data={"contact_id": "c1", "slot_time": "2025-01-15T10:00:00Z"},
        )
    assert response.status_code == 200
    assert "booked" in response.text.lower() or "success" in response.text.lower()


@pytest.mark.asyncio
async def test_book_appointment_missing_fields(client: AsyncClient, location: Location, db):
    location.ghl_location_id = "ghl_loc_123"
    await db.commit()

    response = await client.post(
        f"/loc/{location.slug}/calendars/cal1/book",
        data={"contact_id": "", "slot_time": ""},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_cancel_appointment(client: AsyncClient, location: Location, db):
    location.ghl_location_id = "ghl_loc_123"
    await db.commit()

    with patch("crm.routers.calendars.cancel_appointment", new_callable=AsyncMock, return_value={}):
        response = await client.post(
            f"/loc/{location.slug}/calendars/appointments/apt1/cancel",
        )
    assert response.status_code == 200
    assert "cancelled" in response.text.lower()
