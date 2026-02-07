"""Conversation routes - inbox, messages, send SMS/email."""

from __future__ import annotations

import html
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..models.location import Location
from ..models.contact import Contact
from ..services import conversation_svc
from ..services.messaging_svc import MessagingNotConfigured, send_sms, send_email
from ..tenant.deps import get_current_location

router = APIRouter(tags=["conversations"])
templates = Jinja2Templates(directory=str(settings.templates_dir))


async def _all_locations(db: AsyncSession):
    return list((await db.execute(select(Location).order_by(Location.name))).scalars().all())


@router.get("/loc/{slug}/conversations/")
async def inbox(
    request: Request,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    conversations, total = await conversation_svc.list_conversations(db, location.id)
    return templates.TemplateResponse("conversations/inbox.html", {
        "request": request,
        "location": location,
        "locations": await _all_locations(db),
        "conversations": conversations,
        "total": total,
        "sms_configured": settings.twilio_configured,
        "email_configured": settings.sendgrid_configured,
    })


@router.get("/loc/{slug}/conversations/threads")
async def thread_list(
    request: Request,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    conversations, _ = await conversation_svc.list_conversations(db, location.id)
    return templates.TemplateResponse("conversations/_thread_list.html", {
        "request": request,
        "location": location,
        "conversations": conversations,
    })


@router.get("/loc/{slug}/conversations/{conversation_id}/messages")
async def messages(
    request: Request,
    conversation_id: uuid.UUID,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    conv = await conversation_svc.get_conversation(db, conversation_id)
    if not conv:
        return HTMLResponse('<div class="text-gray-400 p-4">Conversation not found.</div>')
    message_list = await conversation_svc.get_messages(db, conversation_id)
    await conversation_svc.mark_read(db, conversation_id)
    return templates.TemplateResponse("conversations/_messages.html", {
        "request": request,
        "location": location,
        "conversation": conv,
        "messages": message_list,
        "contact": conv.contact,
        "sms_configured": settings.twilio_configured,
        "email_configured": settings.sendgrid_configured,
    })


@router.post("/loc/{slug}/conversations/{contact_id}/sms")
async def reply_sms(
    request: Request,
    contact_id: uuid.UUID,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    message = form.get("message", "").strip()
    if not message:
        return HTMLResponse(
            '<div class="text-red-600 text-sm">Message is required.</div>', status_code=422
        )

    # Get contact phone
    stmt = select(Contact).where(Contact.id == contact_id)
    contact = (await db.execute(stmt)).scalar_one_or_none()
    if not contact or not contact.phone:
        return HTMLResponse(
            '<div class="text-red-600 text-sm">Contact has no phone number.</div>', status_code=422
        )

    try:
        await send_sms(db, location.id, contact_id, contact.phone, message)
        return HTMLResponse('<div class="text-green-600 text-sm font-medium">SMS sent.</div>')
    except MessagingNotConfigured as e:
        return HTMLResponse(
            f'<div class="text-yellow-600 text-sm">{html.escape(str(e))}</div>', status_code=422
        )
    except Exception as e:
        return HTMLResponse(
            f'<div class="text-red-600 text-sm">Failed: {html.escape(str(e))}</div>', status_code=500
        )


@router.post("/loc/{slug}/conversations/{contact_id}/email")
async def reply_email(
    request: Request,
    contact_id: uuid.UUID,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    subject = form.get("subject", "").strip()
    body = form.get("body", "").strip()
    if not subject or not body:
        return HTMLResponse(
            '<div class="text-red-600 text-sm">Subject and body are required.</div>', status_code=422
        )

    stmt = select(Contact).where(Contact.id == contact_id)
    contact = (await db.execute(stmt)).scalar_one_or_none()
    if not contact or not contact.email:
        return HTMLResponse(
            '<div class="text-red-600 text-sm">Contact has no email.</div>', status_code=422
        )

    try:
        await send_email(db, location.id, contact_id, contact.email, subject, body)
        return HTMLResponse('<div class="text-green-600 text-sm font-medium">Email sent.</div>')
    except MessagingNotConfigured as e:
        return HTMLResponse(
            f'<div class="text-yellow-600 text-sm">{html.escape(str(e))}</div>', status_code=422
        )
    except Exception as e:
        return HTMLResponse(
            f'<div class="text-red-600 text-sm">Failed: {html.escape(str(e))}</div>', status_code=500
        )


@router.post("/loc/{slug}/conversations/{conversation_id}/read")
async def mark_read(
    conversation_id: uuid.UUID,
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    await conversation_svc.mark_read(db, conversation_id)
    return HTMLResponse('<div class="text-green-600 text-sm">Marked as read.</div>')
