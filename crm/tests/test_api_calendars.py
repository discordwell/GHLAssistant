"""Test calendar API routes."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from crm.models.calendar import Calendar, AvailabilityWindow
from crm.models.location import Location
from crm.services import calendar_svc


@pytest.mark.asyncio
async def test_calendars_list_page(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/calendars/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_calendars_new_page(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/calendars/new")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_calendars_create(client: AsyncClient, location: Location):
    response = await client.post(
        f"/loc/{location.slug}/calendars/",
        data={"name": "Test Cal", "slot_duration": "30"},
        follow_redirects=False,
    )
    assert response.status_code == 303


@pytest.mark.asyncio
async def test_calendars_detail(
    client: AsyncClient, db: AsyncSession, location: Location
):
    cal = Calendar(
        location_id=location.id,
        name="Detail Cal",
        slot_duration=30,
    )
    db.add(cal)
    await db.commit()
    await db.refresh(cal)

    response = await client.get(f"/loc/{location.slug}/calendars/{cal.id}")
    assert response.status_code == 200
    assert "Detail Cal" in response.text


@pytest.mark.asyncio
async def test_calendars_edit(
    client: AsyncClient, db: AsyncSession, location: Location
):
    cal = Calendar(
        location_id=location.id,
        name="Before Edit",
        slot_duration=30,
    )
    db.add(cal)
    await db.commit()
    await db.refresh(cal)

    response = await client.post(
        f"/loc/{location.slug}/calendars/{cal.id}/edit",
        data={"name": "Updated", "slot_duration": "60"},
        follow_redirects=False,
    )
    assert response.status_code == 303


@pytest.mark.asyncio
async def test_calendars_delete(
    client: AsyncClient, db: AsyncSession, location: Location
):
    cal = Calendar(
        location_id=location.id,
        name="To Delete",
        slot_duration=30,
    )
    db.add(cal)
    await db.commit()
    await db.refresh(cal)

    response = await client.post(
        f"/loc/{location.slug}/calendars/{cal.id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 303


@pytest.mark.asyncio
async def test_calendars_add_availability(
    client: AsyncClient, db: AsyncSession, location: Location
):
    cal = Calendar(
        location_id=location.id,
        name="Avail Cal",
        slot_duration=30,
    )
    db.add(cal)
    await db.commit()
    await db.refresh(cal)

    response = await client.post(
        f"/loc/{location.slug}/calendars/{cal.id}/availability",
        data={"day_of_week": "1", "start_time": "09:00", "end_time": "17:00"},
        follow_redirects=False,
    )
    assert response.status_code == 303


@pytest.mark.asyncio
async def test_calendars_slots(
    client: AsyncClient, db: AsyncSession, location: Location
):
    cal = Calendar(
        location_id=location.id,
        name="Slots Cal",
        slot_duration=30,
    )
    db.add(cal)
    await db.commit()
    await db.refresh(cal)

    # Add availability for Monday (0)
    from datetime import time

    window = AvailabilityWindow(
        calendar_id=cal.id,
        day_of_week=0,
        start_time=time(9, 0),
        end_time=time(17, 0),
    )
    db.add(window)
    await db.commit()

    response = await client.get(
        f"/loc/{location.slug}/calendars/{cal.id}/slots",
        params={"start": "2030-01-07", "end": "2030-01-08"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_calendars_book(
    client: AsyncClient, db: AsyncSession, location: Location
):
    cal = Calendar(
        location_id=location.id,
        name="Book Cal",
        slot_duration=30,
    )
    db.add(cal)
    await db.commit()
    await db.refresh(cal)

    from crm.models.contact import Contact

    contact = Contact(
        location_id=location.id,
        first_name="Book",
        last_name="Person",
        email="book@test.com",
    )
    db.add(contact)
    await db.commit()
    await db.refresh(contact)

    response = await client.post(
        f"/loc/{location.slug}/calendars/{cal.id}/book",
        data={
            "contact_id": str(contact.id),
            "slot_time": "2030-01-07T10:00:00+00:00",
            "title": "Meeting",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


@pytest.mark.asyncio
async def test_calendars_list_empty(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/calendars/")
    assert response.status_code == 200
