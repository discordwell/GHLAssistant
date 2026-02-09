"""Import calendars and appointments from GHL."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.calendar import Calendar, Appointment
from ..models.contact import Contact
from ..models.location import Location
from ..schemas.sync import SyncResult
from .raw_store import upsert_raw_entity


async def import_calendars(
    db: AsyncSession, location: Location, calendars_data: list[dict],
    appointments_data: dict[str, list[dict]] | None = None,
    details_by_calendar: dict[str, dict] | None = None,
) -> SyncResult:
    """Import calendars and appointments from GHL."""
    result = SyncResult()
    appointments_data = appointments_data or {}
    details_by_calendar = details_by_calendar or {}

    for cal_data in calendars_data:
        ghl_id = cal_data.get("id", cal_data.get("_id", ""))
        name = cal_data.get("name", "")
        if not name:
            continue

        detail_payload = details_by_calendar.get(ghl_id)
        if not isinstance(detail_payload, dict):
            detail_payload = {}
        await upsert_raw_entity(
            db,
            location=location,
            entity_type="calendar",
            ghl_id=ghl_id,
            payload={"list": cal_data, "detail": detail_payload},
        )

        stmt = select(Calendar).where(
            Calendar.location_id == location.id, Calendar.ghl_id == ghl_id
        )
        cal = (await db.execute(stmt)).scalar_one_or_none()

        source_payload = detail_payload.get("calendar") if isinstance(detail_payload.get("calendar"), dict) else detail_payload
        if not isinstance(source_payload, dict):
            source_payload = {}

        description = source_payload.get("description", cal_data.get("description"))
        timezone_val = source_payload.get("timezone", cal_data.get("timezone", "America/New_York"))
        slot_duration = source_payload.get("slotDuration", cal_data.get("slotDuration", 30))
        buffer_before = source_payload.get("bufferBefore", cal_data.get("bufferBefore", 0))
        buffer_after = source_payload.get("bufferAfter", cal_data.get("bufferAfter", 0))
        is_active = source_payload.get("isActive", cal_data.get("isActive", True))

        if cal:
            cal.name = name
            cal.description = description
            cal.timezone = timezone_val or cal.timezone
            cal.slot_duration = int(slot_duration) if isinstance(slot_duration, (int, float)) else cal.slot_duration
            cal.buffer_before = int(buffer_before) if isinstance(buffer_before, (int, float)) else cal.buffer_before
            cal.buffer_after = int(buffer_after) if isinstance(buffer_after, (int, float)) else cal.buffer_after
            cal.is_active = bool(is_active) if isinstance(is_active, bool) or isinstance(is_active, int) else cal.is_active
            cal.last_synced_at = datetime.now(timezone.utc)
            result.updated += 1
        else:
            cal = Calendar(
                location_id=location.id, name=name,
                description=description,
                timezone=timezone_val or "America/New_York",
                slot_duration=int(slot_duration) if isinstance(slot_duration, (int, float)) else 30,
                buffer_before=int(buffer_before) if isinstance(buffer_before, (int, float)) else 0,
                buffer_after=int(buffer_after) if isinstance(buffer_after, (int, float)) else 0,
                is_active=bool(is_active) if isinstance(is_active, bool) or isinstance(is_active, int) else True,
                ghl_id=ghl_id,
                ghl_location_id=location.ghl_location_id,
                last_synced_at=datetime.now(timezone.utc),
            )
            db.add(cal)
            await db.flush()
            result.created += 1

        # Import appointments
        for appt_data in appointments_data.get(ghl_id, []):
            a_ghl_id = appt_data.get("id", appt_data.get("_id", ""))
            if not a_ghl_id:
                continue
            await upsert_raw_entity(
                db,
                location=location,
                entity_type="appointment",
                ghl_id=a_ghl_id,
                payload=appt_data,
            )

            stmt = select(Appointment).where(
                Appointment.calendar_id == cal.id, Appointment.ghl_id == a_ghl_id
            )
            appt = (await db.execute(stmt)).scalar_one_or_none()

            # Resolve contact
            contact_id = None
            ghl_contact_id = appt_data.get("contactId", "")
            if ghl_contact_id:
                stmt2 = select(Contact).where(
                    Contact.location_id == location.id, Contact.ghl_id == ghl_contact_id
                )
                contact = (await db.execute(stmt2)).scalar_one_or_none()
                if contact:
                    contact_id = contact.id

            start_str = appt_data.get("startTime", appt_data.get("start", ""))
            end_str = appt_data.get("endTime", appt_data.get("end", ""))
            try:
                start_time = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                end_time = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue

            if appt:
                appt.title = appt_data.get("title")
                appt.status = appt_data.get("status", "confirmed")
                appt.contact_id = contact_id
                appt.start_time = start_time
                appt.end_time = end_time
                appt.last_synced_at = datetime.now(timezone.utc)
            else:
                appt = Appointment(
                    location_id=location.id,
                    calendar_id=cal.id,
                    contact_id=contact_id,
                    title=appt_data.get("title"),
                    notes=appt_data.get("notes"),
                    start_time=start_time,
                    end_time=end_time,
                    status=appt_data.get("status", "confirmed"),
                    ghl_id=a_ghl_id,
                    ghl_location_id=location.ghl_location_id,
                    last_synced_at=datetime.now(timezone.utc),
                )
                db.add(appt)

    await db.commit()
    return result
