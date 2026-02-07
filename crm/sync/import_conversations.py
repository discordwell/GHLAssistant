"""Import conversations and messages from GHL."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.conversation import Conversation, Message
from ..models.contact import Contact
from ..models.location import Location
from ..schemas.sync import SyncResult


async def import_conversations(
    db: AsyncSession, location: Location, conversations_data: list[dict],
    messages_by_conv: dict[str, list[dict]] | None = None,
) -> SyncResult:
    """Import conversations and their messages from GHL."""
    result = SyncResult()
    messages_by_conv = messages_by_conv or {}

    for c_data in conversations_data:
        ghl_id = c_data.get("id", c_data.get("_id", ""))
        if not ghl_id:
            continue

        # Resolve contact
        contact_id = None
        ghl_contact_id = c_data.get("contactId", "")
        if ghl_contact_id:
            stmt = select(Contact).where(
                Contact.location_id == location.id, Contact.ghl_id == ghl_contact_id
            )
            contact = (await db.execute(stmt)).scalar_one_or_none()
            if contact:
                contact_id = contact.id

        stmt = select(Conversation).where(
            Conversation.location_id == location.id, Conversation.ghl_id == ghl_id
        )
        conv = (await db.execute(stmt)).scalar_one_or_none()

        if conv:
            conv.contact_id = contact_id
            conv.last_synced_at = datetime.now(timezone.utc)
            result.updated += 1
        else:
            conv = Conversation(
                location_id=location.id,
                contact_id=contact_id,
                channel=c_data.get("type", "sms"),
                subject=c_data.get("subject"),
                unread_count=c_data.get("unreadCount", 0),
                ghl_id=ghl_id,
                ghl_location_id=location.ghl_location_id,
                last_synced_at=datetime.now(timezone.utc),
            )
            db.add(conv)
            await db.flush()
            result.created += 1

        # Import messages for this conversation
        for m_data in messages_by_conv.get(ghl_id, []):
            m_ghl_id = m_data.get("id", m_data.get("_id", ""))
            if not m_ghl_id:
                continue

            stmt = select(Message).where(
                Message.conversation_id == conv.id,
                Message.provider_id == m_ghl_id,
            )
            existing_msg = (await db.execute(stmt)).scalar_one_or_none()
            if existing_msg:
                continue  # skip duplicate messages

            msg = Message(
                location_id=location.id,
                conversation_id=conv.id,
                contact_id=contact_id,
                direction=m_data.get("direction", "outbound"),
                channel=m_data.get("type", conv.channel or "sms"),
                body=m_data.get("body", ""),
                subject=m_data.get("subject"),
                from_address=m_data.get("from"),
                to_address=m_data.get("to"),
                provider_id=m_ghl_id,
                status=m_data.get("status", "delivered"),
            )
            db.add(msg)

        # Update last_message_at
        last_msg_at = c_data.get("lastMessageDate") or c_data.get("dateUpdated")
        if last_msg_at:
            try:
                conv.last_message_at = datetime.fromisoformat(
                    last_msg_at.replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                pass

    await db.commit()
    return result
