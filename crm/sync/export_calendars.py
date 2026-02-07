"""Export calendar appointments to GHL."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.calendar import Appointment, Calendar
from ..models.contact import Contact
from ..models.location import Location
from ..schemas.sync import SyncResult


async def export_calendars(
    db: AsyncSession, location: Location, ghl,
) -> SyncResult:
    """Export appointments without ghl_id to GHL."""
    result = SyncResult()

    stmt = (
        select(Appointment)
        .where(
            Appointment.location_id == location.id,
            Appointment.ghl_id == None,  # noqa: E711
            Appointment.status != "cancelled",
        )
        .options(selectinload(Appointment.calendar))
    )
    appointments = list((await db.execute(stmt)).scalars().all())

    for appt in appointments:
        if not appt.contact_id:
            result.skipped += 1
            continue

        # Get contact and calendar GHL IDs
        stmt2 = select(Contact).where(Contact.id == appt.contact_id)
        contact = (await db.execute(stmt2)).scalar_one_or_none()

        if not contact or not contact.ghl_id:
            result.skipped += 1
            continue

        if not appt.calendar or not appt.calendar.ghl_id:
            result.skipped += 1
            continue

        try:
            resp = await ghl.calendars.book(
                appt.calendar.ghl_id,
                contact.ghl_id,
                appt.start_time.isoformat(),
                title=appt.title,
                notes=appt.notes,
                location_id=location.ghl_location_id,
            )
            appt_resp = resp.get("appointment", resp)
            appt.ghl_id = appt_resp.get("id", "")
            appt.last_synced_at = datetime.now(timezone.utc)
            result.created += 1
        except Exception as e:
            result.errors.append(f"Appointment export: {e}")

    await db.commit()
    return result
