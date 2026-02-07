"""GHL Conversations routes - two-panel inbox with SMS/email reply."""

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
    fetch_conversations,
    fetch_conversation_messages,
    send_sms,
    send_email,
    mark_conversation_read,
)
from ..tenant.deps import get_current_location

router = APIRouter(tags=["ghl-conversations"])
templates = Jinja2Templates(directory=str(settings.templates_dir))


async def _all_locations(db: AsyncSession):
    return list((await db.execute(select(Location).order_by(Location.name))).scalars().all())


@router.get("/loc/{slug}/conversations/")
async def inbox(
    request: Request,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    ghl_error = None
    conversations = []
    if not location.ghl_location_id:
        ghl_error = "No GHL location linked. Go to Sync to connect."
    else:
        try:
            data = await fetch_conversations(location.ghl_location_id)
            conversations = data.get("conversations", [])
        except GHLNotLinkedError as e:
            ghl_error = str(e)
        except Exception as e:
            ghl_error = f"Failed to load conversations: {e}"

    return templates.TemplateResponse("conversations/inbox.html", {
        "request": request,
        "location": location,
        "locations": await _all_locations(db),
        "conversations": conversations,
        "ghl_error": ghl_error,
    })


@router.get("/loc/{slug}/conversations/threads")
async def thread_list(
    request: Request,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    ghl_error = None
    conversations = []
    if location.ghl_location_id:
        try:
            data = await fetch_conversations(location.ghl_location_id)
            conversations = data.get("conversations", [])
        except Exception as e:
            ghl_error = str(e)

    return templates.TemplateResponse("conversations/_thread_list.html", {
        "request": request,
        "location": location,
        "conversations": conversations,
        "ghl_error": ghl_error,
    })


@router.get("/loc/{slug}/conversations/{conversation_id}/messages")
async def messages(
    request: Request,
    conversation_id: str,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    ghl_error = None
    message_list = []
    contact_id = None

    try:
        data = await fetch_conversation_messages(conversation_id)
        raw = data.get("messages", [])
        if isinstance(raw, dict):
            message_list = raw.get("messages", [])
        elif isinstance(raw, list):
            message_list = raw
        else:
            message_list = []
        # Try to mark as read
        try:
            await mark_conversation_read(conversation_id)
        except Exception:
            pass
        # Extract contact_id from first message if available
        if message_list:
            contact_id = message_list[0].get("contactId", None)
    except Exception as e:
        ghl_error = str(e)

    return templates.TemplateResponse("conversations/_messages.html", {
        "request": request,
        "location": location,
        "messages": message_list,
        "conversation_id": conversation_id,
        "contact_id": contact_id,
        "ghl_error": ghl_error,
    })


@router.post("/loc/{slug}/conversations/{contact_id}/sms")
async def reply_sms(
    request: Request,
    contact_id: str,
    location: Location = Depends(get_current_location),
):
    form = await request.form()
    message = form.get("message", "").strip()
    if not message:
        return HTMLResponse(
            '<div class="text-red-600 text-sm">Message is required.</div>',
            status_code=422,
        )

    try:
        await send_sms(contact_id, message, location.ghl_location_id)
        return HTMLResponse(
            '<div class="text-green-600 text-sm font-medium">SMS sent.</div>'
        )
    except Exception as e:
        return HTMLResponse(
            f'<div class="text-red-600 text-sm">Failed to send: {html.escape(str(e))}</div>',
            status_code=500,
        )


@router.post("/loc/{slug}/conversations/{contact_id}/email")
async def reply_email(
    request: Request,
    contact_id: str,
    location: Location = Depends(get_current_location),
):
    form = await request.form()
    subject = form.get("subject", "").strip()
    body = form.get("body", "").strip()
    if not subject or not body:
        return HTMLResponse(
            '<div class="text-red-600 text-sm">Subject and body are required.</div>',
            status_code=422,
        )

    try:
        await send_email(contact_id, subject, body, location.ghl_location_id)
        return HTMLResponse(
            '<div class="text-green-600 text-sm font-medium">Email sent.</div>'
        )
    except Exception as e:
        return HTMLResponse(
            f'<div class="text-red-600 text-sm">Failed to send: {html.escape(str(e))}</div>',
            status_code=500,
        )
