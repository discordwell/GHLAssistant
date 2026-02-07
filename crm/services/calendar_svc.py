"""Calendar service - CRUD, availability, slot generation, booking."""

from __future__ import annotations

import uuid
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.calendar import Calendar, AvailabilityWindow, Appointment


async def list_calendars(
    db: AsyncSession, location_id: uuid.UUID
) -> list[Calendar]:
    stmt = (
        select(Calendar)
        .where(Calendar.location_id == location_id)
        .options(selectinload(Calendar.availability_windows))
        .order_by(Calendar.name)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_calendar(
    db: AsyncSession, calendar_id: uuid.UUID
) -> Calendar | None:
    stmt = (
        select(Calendar)
        .where(Calendar.id == calendar_id)
        .options(
            selectinload(Calendar.availability_windows),
            selectinload(Calendar.appointments).selectinload(Appointment.contact),
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_calendar(
    db: AsyncSession, location_id: uuid.UUID, **kwargs
) -> Calendar:
    cal = Calendar(location_id=location_id, **kwargs)
    db.add(cal)
    await db.commit()
    await db.refresh(cal)
    return cal


async def update_calendar(
    db: AsyncSession, calendar_id: uuid.UUID, **kwargs
) -> Calendar | None:
    cal = await get_calendar(db, calendar_id)
    if not cal:
        return None
    for k, v in kwargs.items():
        setattr(cal, k, v)
    await db.commit()
    await db.refresh(cal)
    return cal


async def delete_calendar(db: AsyncSession, calendar_id: uuid.UUID) -> bool:
    stmt = select(Calendar).where(Calendar.id == calendar_id)
    cal = (await db.execute(stmt)).scalar_one_or_none()
    if not cal:
        return False
    await db.delete(cal)
    await db.commit()
    return True


async def add_availability(
    db: AsyncSession, calendar_id: uuid.UUID,
    day_of_week: int, start_time: time, end_time: time,
) -> AvailabilityWindow:
    window = AvailabilityWindow(
        calendar_id=calendar_id,
        day_of_week=day_of_week,
        start_time=start_time,
        end_time=end_time,
    )
    db.add(window)
    await db.commit()
    await db.refresh(window)
    return window


async def delete_availability(db: AsyncSession, window_id: uuid.UUID) -> bool:
    stmt = select(AvailabilityWindow).where(AvailabilityWindow.id == window_id)
    window = (await db.execute(stmt)).scalar_one_or_none()
    if not window:
        return False
    await db.delete(window)
    await db.commit()
    return True


async def generate_slots(
    db: AsyncSession,
    calendar_id: uuid.UUID,
    start_date: datetime,
    end_date: datetime,
) -> list[dict]:
    """Generate available time slots for a calendar within date range."""
    cal = await get_calendar(db, calendar_id)
    if not cal or not cal.is_active:
        return []

    # Get existing appointments in range
    stmt = select(Appointment).where(
        Appointment.calendar_id == calendar_id,
        Appointment.start_time >= start_date,
        Appointment.end_time <= end_date,
        Appointment.status != "cancelled",
    )
    result = await db.execute(stmt)
    booked = list(result.scalars().all())
    booked_times = set()
    for a in booked:
        st = a.start_time if a.start_time.tzinfo else a.start_time.replace(tzinfo=timezone.utc)
        et = a.end_time if a.end_time.tzinfo else a.end_time.replace(tzinfo=timezone.utc)
        booked_times.add((st, et))

    slots = []
    current = start_date
    duration = timedelta(minutes=cal.slot_duration)
    buffer_before = timedelta(minutes=cal.buffer_before)
    buffer_after = timedelta(minutes=cal.buffer_after)

    while current.date() <= end_date.date():
        dow = current.weekday()  # 0=Monday
        windows = [w for w in cal.availability_windows if w.day_of_week == dow]

        for window in windows:
            slot_start_dt = current.replace(
                hour=window.start_time.hour, minute=window.start_time.minute, second=0, microsecond=0
            )
            window_end_dt = current.replace(
                hour=window.end_time.hour, minute=window.end_time.minute, second=0, microsecond=0
            )

            while slot_start_dt + duration <= window_end_dt:
                slot_end_dt = slot_start_dt + duration
                # Check buffer zone doesn't overlap booked
                buf_start = slot_start_dt - buffer_before
                buf_end = slot_end_dt + buffer_after

                is_booked = any(
                    buf_start < booked_end and buf_end > booked_start
                    for booked_start, booked_end in booked_times
                )

                if not is_booked and slot_start_dt > datetime.now(timezone.utc):
                    slots.append({
                        "start": slot_start_dt.isoformat(),
                        "end": slot_end_dt.isoformat(),
                        "date": slot_start_dt.strftime("%Y-%m-%d"),
                        "time": slot_start_dt.strftime("%H:%M"),
                    })

                slot_start_dt += duration

        current += timedelta(days=1)

    return slots


async def book_appointment(
    db: AsyncSession, location_id: uuid.UUID, calendar_id: uuid.UUID,
    contact_id: uuid.UUID | None, start_time: datetime, end_time: datetime,
    title: str | None = None, notes: str | None = None,
) -> Appointment:
    appt = Appointment(
        location_id=location_id,
        calendar_id=calendar_id,
        contact_id=contact_id,
        start_time=start_time,
        end_time=end_time,
        title=title,
        notes=notes,
    )
    db.add(appt)
    await db.commit()
    await db.refresh(appt)
    return appt


async def cancel_appointment(db: AsyncSession, appointment_id: uuid.UUID) -> bool:
    stmt = select(Appointment).where(Appointment.id == appointment_id)
    appt = (await db.execute(stmt)).scalar_one_or_none()
    if not appt:
        return False
    appt.status = "cancelled"
    await db.commit()
    return True
