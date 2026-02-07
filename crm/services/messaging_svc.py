"""Messaging service — Twilio SMS + SendGrid Email."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models.conversation import Conversation, Message

log = logging.getLogger(__name__)


class MessagingNotConfigured(Exception):
    """Raised when Twilio/SendGrid credentials are missing."""


async def send_sms(
    db: AsyncSession,
    location_id,
    contact_id,
    to_phone: str,
    body: str,
) -> Message:
    """Send SMS via Twilio and record the message."""
    if not settings.twilio_configured:
        raise MessagingNotConfigured("Twilio is not configured. Set CRM_TWILIO_* env vars.")

    from twilio.rest import Client
    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)

    tw_msg = client.messages.create(
        body=body,
        from_=settings.twilio_from_number,
        to=to_phone,
    )

    conv = await _get_or_create_conversation(db, location_id, contact_id, "sms")
    msg = Message(
        location_id=location_id,
        conversation_id=conv.id,
        contact_id=contact_id,
        direction="outbound",
        channel="sms",
        body=body,
        from_address=settings.twilio_from_number,
        to_address=to_phone,
        provider_id=tw_msg.sid,
        status="sent",
    )
    db.add(msg)
    conv.last_message_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(msg)
    return msg


async def send_email(
    db: AsyncSession,
    location_id,
    contact_id,
    to_email: str,
    subject: str,
    html_body: str,
) -> Message:
    """Send email via SendGrid and record the message."""
    if not settings.sendgrid_configured:
        raise MessagingNotConfigured("SendGrid is not configured. Set CRM_SENDGRID_* env vars.")

    import sendgrid
    from sendgrid.helpers.mail import Mail, Email, To, Content

    sg = sendgrid.SendGridAPIClient(api_key=settings.sendgrid_api_key)
    from_email = Email(settings.sendgrid_from_email, settings.sendgrid_from_name)
    mail = Mail(
        from_email=from_email,
        to_emails=To(to_email),
        subject=subject,
        html_content=Content("text/html", html_body),
    )
    response = sg.client.mail.send.post(request_body=mail.get())
    provider_id = None
    if hasattr(response, "headers"):
        provider_id = response.headers.get("X-Message-Id")

    conv = await _get_or_create_conversation(db, location_id, contact_id, "email")
    msg = Message(
        location_id=location_id,
        conversation_id=conv.id,
        contact_id=contact_id,
        direction="outbound",
        channel="email",
        body=html_body,
        subject=subject,
        from_address=settings.sendgrid_from_email,
        to_address=to_email,
        provider_id=provider_id,
        status="sent",
    )
    db.add(msg)
    conv.last_message_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(msg)
    return msg


async def handle_twilio_status_callback(db: AsyncSession, data: dict) -> None:
    """Update message status from Twilio webhook."""
    sid = data.get("MessageSid", "")
    status = data.get("MessageStatus", "")
    if not sid:
        return
    stmt = select(Message).where(Message.provider_id == sid)
    msg = (await db.execute(stmt)).scalar_one_or_none()
    if msg:
        msg.status = status
        msg.status_detail = data.get("ErrorMessage")
        await db.commit()


async def handle_twilio_inbound(
    db: AsyncSession, data: dict, location_id
) -> Message:
    """Create inbound SMS message from Twilio webhook."""
    from_number = data.get("From", "")
    body = data.get("Body", "")
    sid = data.get("MessageSid", "")

    # Try to find contact by phone
    from ..models.contact import Contact
    stmt = select(Contact).where(
        Contact.location_id == location_id, Contact.phone == from_number
    )
    contact = (await db.execute(stmt)).scalar_one_or_none()
    contact_id = contact.id if contact else None

    conv = await _get_or_create_conversation(db, location_id, contact_id, "sms")
    msg = Message(
        location_id=location_id,
        conversation_id=conv.id,
        contact_id=contact_id,
        direction="inbound",
        channel="sms",
        body=body,
        from_address=from_number,
        to_address=settings.twilio_from_number,
        provider_id=sid,
        status="received",
    )
    db.add(msg)
    conv.last_message_at = datetime.now(timezone.utc)
    conv.unread_count += 1
    await db.commit()
    await db.refresh(msg)
    return msg


async def handle_sendgrid_inbound(
    db: AsyncSession, data: dict, location_id
) -> Message:
    """Create inbound email message from SendGrid Inbound Parse webhook."""
    from_email = data.get("from", data.get("sender_email", ""))
    subject = data.get("subject", "")
    body = data.get("html", data.get("text", ""))

    from ..models.contact import Contact
    stmt = select(Contact).where(
        Contact.location_id == location_id, Contact.email == from_email
    )
    contact = (await db.execute(stmt)).scalar_one_or_none()
    contact_id = contact.id if contact else None

    conv = await _get_or_create_conversation(db, location_id, contact_id, "email")
    msg = Message(
        location_id=location_id,
        conversation_id=conv.id,
        contact_id=contact_id,
        direction="inbound",
        channel="email",
        body=body,
        subject=subject,
        from_address=from_email,
        to_address=settings.sendgrid_from_email,
        status="received",
    )
    db.add(msg)
    conv.last_message_at = datetime.now(timezone.utc)
    conv.unread_count += 1
    await db.commit()
    await db.refresh(msg)
    return msg


async def _get_or_create_conversation(
    db: AsyncSession, location_id, contact_id, channel: str
) -> Conversation:
    """Get existing conversation or create a new one."""
    if contact_id:
        stmt = select(Conversation).where(
            Conversation.location_id == location_id,
            Conversation.contact_id == contact_id,
            Conversation.channel == channel,
            Conversation.is_archived == False,  # noqa: E712
        )
        conv = (await db.execute(stmt)).scalar_one_or_none()
        if conv:
            return conv

    conv = Conversation(
        location_id=location_id,
        contact_id=contact_id,
        channel=channel,
        last_message_at=datetime.now(timezone.utc),
    )
    db.add(conv)
    await db.flush()
    return conv
