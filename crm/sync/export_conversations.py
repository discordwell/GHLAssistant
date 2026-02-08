"""Export conversations to GHL."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.conversation import Message
from ..models.contact import Contact
from ..models.location import Location
from ..schemas.sync import SyncResult


def _extract_message_id(resp: dict) -> str:
    """Extract a provider message id from common API response shapes."""
    if not isinstance(resp, dict):
        return ""

    for key in ("id", "_id", "messageId"):
        value = resp.get(key)
        if isinstance(value, str) and value:
            return value

    message = resp.get("message")
    if isinstance(message, dict):
        for key in ("id", "_id", "messageId"):
            value = message.get(key)
            if isinstance(value, str) and value:
                return value

    data = resp.get("data")
    if isinstance(data, dict):
        for key in ("id", "_id", "messageId"):
            value = data.get(key)
            if isinstance(value, str) and value:
                return value

    return ""


async def export_conversations(
    db: AsyncSession, location: Location, ghl,
) -> SyncResult:
    """Export outbound messages without provider IDs to GHL."""
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
            provider_resp: dict = {}
            if msg.channel == "sms" and msg.body:
                provider_resp = await ghl.conversations.send_sms(
                    contact.ghl_id, msg.body, location_id=location.ghl_location_id
                )
                result.created += 1
            elif msg.channel == "email" and msg.body and msg.subject:
                provider_resp = await ghl.conversations.send_email(
                    contact.ghl_id, msg.subject, msg.body,
                    location_id=location.ghl_location_id,
                )
                result.created += 1
            else:
                result.skipped += 1
                continue

            provider_id = _extract_message_id(provider_resp)
            if not provider_id:
                # Mark as exported even when provider id isn't returned to prevent duplicates.
                provider_id = f"exported:{msg.id}"
            msg.provider_id = provider_id
            msg.status = "sent"
            msg.status_detail = "exported_to_ghl"
        except Exception as e:
            result.errors.append(f"Message export error: {e}")

    await db.commit()
    return result
