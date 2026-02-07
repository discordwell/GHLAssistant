"""Calendar routes - CRUD, availability, slots, booking."""

from __future__ import annotations

import uuid
from datetime import datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..models.location import Location
from ..models.contact import Contact
from ..services import calendar_svc, contact_svc
from ..tenant.deps import get_current_location

router = APIRouter(tags=["calendars"])
templates = Jinja2Templates(directory=str(settings.templates_dir))


async def _all_locations(db: AsyncSession):
    return list((await db.execute(select(Location).order_by(Location.name))).scalars().all())


@router.get("/loc/{slug}/calendars/")
async def calendar_list(
    request: Request,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    calendars = await calendar_svc.list_calendars(db, location.id)
    return templates.TemplateResponse("calendars/list.html", {
        "request": request,
        "location": location,
        "locations": await _all_locations(db),
        "calendars": calendars,
    })


@router.get("/loc/{slug}/calendars/new")
async def calendar_form(
    request: Request,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    return templates.TemplateResponse("calendars/form.html", {
        "request": request,
        "location": location,
        "locations": await _all_locations(db),
        "calendar": None,
    })


@router.post("/loc/{slug}/calendars/")
async def calendar_create(
    request: Request,
    slug: str,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    data = {
        "name": form.get("name", "").strip(),
        "description": form.get("description", "").strip() or None,
        "timezone": form.get("timezone", "America/New_York").strip(),
        "slot_duration": int(form.get("slot_duration", "30")),
        "buffer_before": int(form.get("buffer_before", "0")),
        "buffer_after": int(form.get("buffer_after", "0")),
    }
    cal = await calendar_svc.create_calendar(db, location.id, **data)
    return RedirectResponse(f"/loc/{slug}/calendars/{cal.id}", status_code=303)


@router.get("/loc/{slug}/calendars/{calendar_id}")
async def calendar_detail(
    request: Request,
    calendar_id: uuid.UUID,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    cal = await calendar_svc.get_calendar(db, calendar_id)
    if not cal or cal.location_id != location.id:
        return RedirectResponse(f"/loc/{location.slug}/calendars/", status_code=303)
    contacts, _ = await contact_svc.list_contacts(db, location.id, limit=200)
    return templates.TemplateResponse("calendars/detail.html", {
        "request": request,
        "location": location,
        "locations": await _all_locations(db),
        "calendar": cal,
        "contacts": contacts,
        "day_names": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    })


@router.post("/loc/{slug}/calendars/{calendar_id}/edit")
async def calendar_update(
    request: Request,
    slug: str,
    calendar_id: uuid.UUID,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    data = {
        "name": form.get("name", "").strip(),
        "description": form.get("description", "").strip() or None,
        "timezone": form.get("timezone", "").strip(),
        "slot_duration": int(form.get("slot_duration", "30")),
        "buffer_before": int(form.get("buffer_before", "0")),
        "buffer_after": int(form.get("buffer_after", "0")),
        "is_active": form.get("is_active") == "on",
    }
    await calendar_svc.update_calendar(db, calendar_id, **data)
    return RedirectResponse(f"/loc/{slug}/calendars/{calendar_id}", status_code=303)


@router.post("/loc/{slug}/calendars/{calendar_id}/delete")
async def calendar_delete(
    slug: str,
    calendar_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    await calendar_svc.delete_calendar(db, calendar_id)
    return RedirectResponse(f"/loc/{slug}/calendars/", status_code=303)


@router.post("/loc/{slug}/calendars/{calendar_id}/availability")
async def add_availability(
    request: Request,
    slug: str,
    calendar_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    day = int(form.get("day_of_week", "0"))
    start = time.fromisoformat(form.get("start_time", "09:00"))
    end = time.fromisoformat(form.get("end_time", "17:00"))
    await calendar_svc.add_availability(db, calendar_id, day, start, end)
    return RedirectResponse(f"/loc/{slug}/calendars/{calendar_id}", status_code=303)


@router.post("/loc/{slug}/calendars/{calendar_id}/availability/{window_id}/delete")
async def delete_availability(
    slug: str,
    calendar_id: uuid.UUID,
    window_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    await calendar_svc.delete_availability(db, window_id)
    return RedirectResponse(f"/loc/{slug}/calendars/{calendar_id}", status_code=303)


@router.get("/loc/{slug}/calendars/{calendar_id}/slots")
async def calendar_slots(
    request: Request,
    calendar_id: uuid.UUID,
    start: str = "",
    end: str = "",
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    slots = []
    error = None
    if not start:
        error = "Start date is required."
    else:
        try:
            start_dt = datetime.fromisoformat(start + "T00:00:00+00:00")
            end_dt = datetime.fromisoformat((end or start) + "T23:59:59+00:00")
            slots = await calendar_svc.generate_slots(db, calendar_id, start_dt, end_dt)
        except Exception as e:
            error = str(e)

    return templates.TemplateResponse("calendars/_slots.html", {
        "request": request,
        "location": location,
        "calendar_id": calendar_id,
        "slots": slots,
        "error": error,
    })


@router.post("/loc/{slug}/calendars/{calendar_id}/book")
async def book(
    request: Request,
    slug: str,
    calendar_id: uuid.UUID,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    contact_id_str = form.get("contact_id", "").strip()
    slot_time_str = form.get("slot_time", "").strip()
    title = form.get("title", "").strip() or None
    notes = form.get("notes", "").strip() or None

    if not contact_id_str or not slot_time_str:
        return HTMLResponse(
            '<div class="text-red-600 text-sm">Contact and time slot required.</div>', status_code=422
        )

    cal = await calendar_svc.get_calendar(db, calendar_id)
    start_time = datetime.fromisoformat(slot_time_str)
    end_time = start_time + timedelta(minutes=cal.slot_duration if cal else 30)

    await calendar_svc.book_appointment(
        db, location.id, calendar_id,
        uuid.UUID(contact_id_str), start_time, end_time,
        title=title, notes=notes,
    )
    return RedirectResponse(f"/loc/{slug}/calendars/{calendar_id}", status_code=303)


@router.post("/loc/{slug}/calendars/appointments/{appointment_id}/cancel")
async def cancel(
    slug: str,
    appointment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    await calendar_svc.cancel_appointment(db, appointment_id)
    return HTMLResponse('<div class="text-green-600 text-sm font-medium">Appointment cancelled.</div>')
