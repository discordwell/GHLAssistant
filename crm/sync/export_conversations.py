"""Export conversations to GHL."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.conversation import Message
from ..models.contact import Contact
from ..models.location import Location
from ..schemas.sync import SyncResult


async def export_conversations(
    db: AsyncSession, location: Location, ghl,
) -> SyncResult:
    """Export outbound messages without ghl_id to GHL."""
    result = SyncResult()

    stmt = (
        select(Message)
        .where(
            Message.location_id == location.id,
            Message.direction == "outbound",
            Message.provider_id == None,  # noqa: E711
        )
    )
    messages = list((await db.execute(stmt)).scalars().all())

    for msg in messages:
        if not msg.contact_id:
            result.skipped += 1
            continue

        # Get contact's GHL ID
        stmt2 = select(Contact).where(Contact.id == msg.contact_id)
        contact = (await db.execute(stmt2)).scalar_one_or_none()
        if not contact or not contact.ghl_id:
            result.skipped += 1
            continue

        try:
            if msg.channel == "sms" and msg.body:
                await ghl.conversations.send_sms(
                    contact.ghl_id, msg.body, location_id=location.ghl_location_id
                )
                result.created += 1
            elif msg.channel == "email" and msg.body and msg.subject:
                await ghl.conversations.send_email(
                    contact.ghl_id, msg.subject, msg.body,
                    location_id=location.ghl_location_id,
                )
                result.created += 1
            else:
                result.skipped += 1
                continue

            msg.status = "sent"
        except Exception as e:
            result.errors.append(f"Message export error: {e}")

    await db.commit()
    return result
