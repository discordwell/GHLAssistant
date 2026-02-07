"""GHL Calendars routes - list calendars, view slots, book/cancel appointments."""

from __future__ import annotations

import html

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..models.location import Location
from ..services.ghl_svc import (
    GHLNotLinkedError,
    fetch_calendars,
    fetch_calendar_slots,
    book_appointment,
    cancel_appointment,
)
from ..tenant.deps import get_current_location

router = APIRouter(tags=["ghl-calendars"])
templates = Jinja2Templates(directory=str(settings.templates_dir))


async def _all_locations(db: AsyncSession):
    return list((await db.execute(select(Location).order_by(Location.name))).scalars().all())


@router.get("/loc/{slug}/calendars/")
async def calendar_list(
    request: Request,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    ghl_error = None
    calendars = []
    if not location.ghl_location_id:
        ghl_error = "No GHL location linked. Go to Sync to connect."
    else:
        try:
            data = await fetch_calendars(location.ghl_location_id)
            calendars = data.get("calendars", [])
        except GHLNotLinkedError as e:
            ghl_error = str(e)
        except Exception as e:
            ghl_error = f"Failed to load calendars: {e}"

    return templates.TemplateResponse("calendars/list.html", {
        "request": request,
        "location": location,
        "locations": await _all_locations(db),
        "calendars": calendars,
        "ghl_error": ghl_error,
    })


@router.get("/loc/{slug}/calendars/{calendar_id}/slots")
async def calendar_slots(
    request: Request,
    calendar_id: str,
    start: str = "",
    end: str = "",
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    ghl_error = None
    slots = {}
    if not location.ghl_location_id:
        ghl_error = "No GHL location linked."
    elif not start:
        ghl_error = "Start date is required (YYYY-MM-DD)."
    else:
        try:
            end_date = end or start
            tz = location.timezone or "America/New_York"
            data = await fetch_calendar_slots(calendar_id, start, end_date, timezone=tz)
            slots = data.get("slots", data.get("availableSlots", {}))
        except GHLNotLinkedError as e:
            ghl_error = str(e)
        except Exception as e:
            ghl_error = f"Failed to load slots: {e}"

    return templates.TemplateResponse("calendars/_slots.html", {
        "request": request,
        "location": location,
        "calendar_id": calendar_id,
        "slots": slots,
        "ghl_error": ghl_error,
    })


@router.post("/loc/{slug}/calendars/{calendar_id}/book")
async def book(
    request: Request,
    calendar_id: str,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    contact_id = form.get("contact_id", "").strip()
    slot_time = form.get("slot_time", "").strip()
    title = form.get("title", "").strip() or None
    notes = form.get("notes", "").strip() or None

    if not contact_id or not slot_time:
        return HTMLResponse(
            '<div class="text-red-600 text-sm">Contact ID and slot time are required.</div>',
            status_code=422,
        )

    try:
        await book_appointment(
            calendar_id, contact_id, slot_time, location.ghl_location_id,
            title=title, notes=notes,
        )
        return HTMLResponse(
            '<div class="text-green-600 text-sm font-medium">Appointment booked successfully.</div>'
        )
    except Exception as e:
        return HTMLResponse(
            f'<div class="text-red-600 text-sm">Booking failed: {html.escape(str(e))}</div>',
            status_code=500,
        )


@router.post("/loc/{slug}/calendars/appointments/{appointment_id}/cancel")
async def cancel(
    request: Request,
    appointment_id: str,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    try:
        await cancel_appointment(appointment_id)
        return HTMLResponse(
            '<div class="text-green-600 text-sm font-medium">Appointment cancelled.</div>'
        )
    except Exception as e:
        return HTMLResponse(
            f'<div class="text-red-600 text-sm">Cancel failed: {html.escape(str(e))}</div>',
            status_code=500,
        )
