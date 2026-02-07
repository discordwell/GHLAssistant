"""Test calendar service."""

from __future__ import annotations

import uuid
from datetime import datetime, time, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from crm.models.contact import Contact
from crm.models.location import Location
from crm.services import calendar_svc


@pytest.mark.asyncio
async def test_create_and_list_calendars(db: AsyncSession, location: Location):
    await calendar_svc.create_calendar(db, location.id, name="Morning Cal")
    await calendar_svc.create_calendar(db, location.id, name="Afternoon Cal")

    cals = await calendar_svc.list_calendars(db, location.id)
    assert len(cals) == 2
    names = [c.name for c in cals]
    assert "Afternoon Cal" in names
    assert "Morning Cal" in names


@pytest.mark.asyncio
async def test_get_calendar(db: AsyncSession, location: Location):
    cal = await calendar_svc.create_calendar(
        db, location.id, name="Test Cal", timezone="America/Chicago"
    )
    fetched = await calendar_svc.get_calendar(db, cal.id)
    assert fetched is not None
    assert fetched.name == "Test Cal"
    assert fetched.timezone == "America/Chicago"


@pytest.mark.asyncio
async def test_get_calendar_not_found(db: AsyncSession, location: Location):
    result = await calendar_svc.get_calendar(db, uuid.uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_update_calendar(db: AsyncSession, location: Location):
    cal = await calendar_svc.create_calendar(db, location.id, name="Old Name")
    updated = await calendar_svc.update_calendar(
        db, cal.id, name="New Name", slot_duration=60
    )
    assert updated is not None
    assert updated.name == "New Name"
    assert updated.slot_duration == 60


@pytest.mark.asyncio
async def test_delete_calendar(db: AsyncSession, location: Location):
    cal = await calendar_svc.create_calendar(db, location.id, name="To Delete")
    result = await calendar_svc.delete_calendar(db, cal.id)
    assert result is True

    fetched = await calendar_svc.get_calendar(db, cal.id)
    assert fetched is None


@pytest.mark.asyncio
async def test_add_availability(db: AsyncSession, location: Location):
    cal = await calendar_svc.create_calendar(db, location.id, name="Avail Cal")
    window = await calendar_svc.add_availability(
        db, cal.id, day_of_week=0, start_time=time(9, 0), end_time=time(17, 0)
    )
    assert window.day_of_week == 0
    assert window.start_time == time(9, 0)
    assert window.end_time == time(17, 0)
    assert window.calendar_id == cal.id


@pytest.mark.asyncio
async def test_delete_availability(db: AsyncSession, location: Location):
    cal = await calendar_svc.create_calendar(db, location.id, name="Del Avail Cal")
    window = await calendar_svc.add_availability(
        db, cal.id, day_of_week=1, start_time=time(10, 0), end_time=time(14, 0)
    )
    result = await calendar_svc.delete_availability(db, window.id)
    assert result is True

    # Verify it's gone by re-fetching calendar
    fetched = await calendar_svc.get_calendar(db, cal.id)
    assert fetched is not None
    assert len(fetched.availability_windows) == 0


@pytest.mark.asyncio
async def test_generate_slots(db: AsyncSession, location: Location):
    cal = await calendar_svc.create_calendar(
        db, location.id, name="Slot Cal", slot_duration=30
    )
    # 2030-01-07 is a Monday (day_of_week=0)
    await calendar_svc.add_availability(
        db, cal.id, day_of_week=0, start_time=time(9, 0), end_time=time(11, 0)
    )

    start = datetime(2030, 1, 7, 0, 0, tzinfo=timezone.utc)
    end = datetime(2030, 1, 7, 23, 59, tzinfo=timezone.utc)

    slots = await calendar_svc.generate_slots(db, cal.id, start, end)
    # 9:00-11:00 with 30 min slots = 4 slots (9:00, 9:30, 10:00, 10:30)
    assert len(slots) == 4
    assert slots[0]["time"] == "09:00"
    assert slots[-1]["time"] == "10:30"


@pytest.mark.asyncio
async def test_generate_slots_no_availability(db: AsyncSession, location: Location):
    cal = await calendar_svc.create_calendar(
        db, location.id, name="No Avail Cal", slot_duration=30
    )
    start = datetime(2030, 1, 7, 0, 0, tzinfo=timezone.utc)
    end = datetime(2030, 1, 7, 23, 59, tzinfo=timezone.utc)

    slots = await calendar_svc.generate_slots(db, cal.id, start, end)
    assert slots == []


@pytest.mark.asyncio
async def test_book_appointment(db: AsyncSession, location: Location):
    cal = await calendar_svc.create_calendar(db, location.id, name="Book Cal")
    contact = Contact(location_id=location.id, first_name="Booker")
    db.add(contact)
    await db.commit()
    await db.refresh(contact)

    start_time = datetime(2030, 1, 7, 9, 0, tzinfo=timezone.utc)
    end_time = datetime(2030, 1, 7, 9, 30, tzinfo=timezone.utc)
    appt = await calendar_svc.book_appointment(
        db, location.id, cal.id, contact.id, start_time, end_time,
        title="Consultation", notes="First visit"
    )
    assert appt.title == "Consultation"
    assert appt.notes == "First visit"
    assert appt.status == "confirmed"
    assert appt.contact_id == contact.id


@pytest.mark.asyncio
async def test_cancel_appointment(db: AsyncSession, location: Location):
    cal = await calendar_svc.create_calendar(db, location.id, name="Cancel Cal")
    start_time = datetime(2030, 1, 7, 10, 0, tzinfo=timezone.utc)
    end_time = datetime(2030, 1, 7, 10, 30, tzinfo=timezone.utc)
    appt = await calendar_svc.book_appointment(
        db, location.id, cal.id, None, start_time, end_time, title="Cancel Me"
    )
    assert appt.status == "confirmed"

    result = await calendar_svc.cancel_appointment(db, appt.id)
    assert result is True

    # Re-fetch via calendar to verify status
    fetched_cal = await calendar_svc.get_calendar(db, cal.id)
    assert fetched_cal is not None
    cancelled = [a for a in fetched_cal.appointments if a.id == appt.id]
    assert len(cancelled) == 1
    assert cancelled[0].status == "cancelled"


@pytest.mark.asyncio
async def test_generate_slots_excludes_booked(db: AsyncSession, location: Location):
    cal = await calendar_svc.create_calendar(
        db, location.id, name="Exclude Cal", slot_duration=30
    )
    # Monday availability 9:00-11:00
    await calendar_svc.add_availability(
        db, cal.id, day_of_week=0, start_time=time(9, 0), end_time=time(11, 0)
    )

    # Book the 9:00-9:30 slot
    booked_start = datetime(2030, 1, 7, 9, 0, tzinfo=timezone.utc)
    booked_end = datetime(2030, 1, 7, 9, 30, tzinfo=timezone.utc)
    await calendar_svc.book_appointment(
        db, location.id, cal.id, None, booked_start, booked_end, title="Booked"
    )

    start = datetime(2030, 1, 7, 0, 0, tzinfo=timezone.utc)
    end = datetime(2030, 1, 7, 23, 59, tzinfo=timezone.utc)

    slots = await calendar_svc.generate_slots(db, cal.id, start, end)
    # Should have 3 slots instead of 4 (9:30, 10:00, 10:30)
    assert len(slots) == 3
    times = [s["time"] for s in slots]
    assert "09:00" not in times
    assert "09:30" in times
