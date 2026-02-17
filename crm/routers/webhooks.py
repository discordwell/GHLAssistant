"""Webhook routes for Twilio/SendGrid callbacks."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..security.webhooks import verify_sendgrid_inbound_auth, verify_twilio_signature
from ..services.messaging_svc import handle_twilio_status_callback, handle_twilio_inbound, handle_sendgrid_inbound

router = APIRouter(tags=["webhooks"])


@router.post("/webhooks/twilio/status")
async def twilio_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    data = dict(form)
    verify_twilio_signature(request, data)
    await handle_twilio_status_callback(db, data)
    return HTMLResponse("OK")


@router.post("/webhooks/twilio/inbound")
async def twilio_inbound(
    request: Request,
    db: AsyncSession = Depends(get_db),
    location_id: str = "",
):
    form = await request.form()
    data = dict(form)
    verify_twilio_signature(request, data)
    if location_id:
        import uuid
        await handle_twilio_inbound(db, data, uuid.UUID(location_id))
    return HTMLResponse("OK")


@router.post("/webhooks/sendgrid/inbound")
async def sendgrid_inbound(
    request: Request,
    db: AsyncSession = Depends(get_db),
    location_id: str = "",
):
    verify_sendgrid_inbound_auth(request)
    form = await request.form()
    data = dict(form)
    if location_id:
        import uuid
        await handle_sendgrid_inbound(db, data, uuid.UUID(location_id))
    return HTMLResponse("OK")
