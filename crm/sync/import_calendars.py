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
) -> SyncResult:
    """Import calendars and appointments from GHL."""
    result = SyncResult()
    appointments_data = appointments_data or {}

    for cal_data in calendars_data:
        ghl_id = cal_data.get("id", cal_data.get("_id", ""))
        name = cal_data.get("name", "")
        if not name:
            continue
        await upsert_raw_entity(
            db,
            location=location,
            entity_type="calendar",
            ghl_id=ghl_id,
            payload=cal_data,
        )

        stmt = select(Calendar).where(
            Calendar.location_id == location.id, Calendar.ghl_id == ghl_id
        )
        cal = (await db.execute(stmt)).scalar_one_or_none()

        if cal:
            cal.name = name
            cal.description = cal_data.get("description")
            cal.last_synced_at = datetime.now(timezone.utc)
            result.updated += 1
        else:
            cal = Calendar(
                location_id=location.id, name=name,
                description=cal_data.get("description"),
                timezone=cal_data.get("timezone", "America/New_York"),
                slot_duration=cal_data.get("slotDuration", 30),
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
