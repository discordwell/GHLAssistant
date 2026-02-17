"""Campaign routes - CRUD campaigns, steps, enrollment, trigger."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..models.location import Location
from ..services import campaign_svc, contact_svc
from ..tenant.deps import get_current_location

router = APIRouter(tags=["campaigns"])
templates = Jinja2Templates(directory=str(settings.templates_dir))
templates.env.globals["app_urls"] = settings.app_urls


async def _all_locations(db: AsyncSession):
    return list((await db.execute(select(Location).order_by(Location.name))).scalars().all())


@router.get("/loc/{slug}/campaigns/")
async def campaign_list(
    request: Request,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    campaigns = await campaign_svc.list_campaigns(db, location.id)
    return templates.TemplateResponse("campaigns/list.html", {
        "request": request,
        "location": location,
        "locations": await _all_locations(db),
        "campaigns": campaigns,
    })


@router.get("/loc/{slug}/campaigns/new")
async def campaign_create_page(
    request: Request,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    return templates.TemplateResponse("campaigns/form.html", {
        "request": request,
        "location": location,
        "locations": await _all_locations(db),
        "campaign": None,
    })


@router.post("/loc/{slug}/campaigns/")
async def campaign_create(
    request: Request,
    slug: str,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    data = {
        "name": form.get("name", "").strip(),
        "description": form.get("description", "").strip() or None,
    }
    c = await campaign_svc.create_campaign(db, location.id, **data)
    return RedirectResponse(f"/loc/{slug}/campaigns/{c.id}", status_code=303)


@router.get("/loc/{slug}/campaigns/{campaign_id}")
async def campaign_detail(
    request: Request,
    campaign_id: uuid.UUID,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
    tab: str = "steps",
):
    campaign = await campaign_svc.get_campaign(db, campaign_id)
    if not campaign or campaign.location_id != location.id:
        return RedirectResponse(f"/loc/{location.slug}/campaigns/", status_code=303)
    contacts, _ = await contact_svc.list_contacts(db, location.id, limit=200)
    return templates.TemplateResponse("campaigns/detail.html", {
        "request": request,
        "location": location,
        "locations": await _all_locations(db),
        "campaign": campaign,
        "contacts": contacts,
        "tab": tab,
    })


@router.post("/loc/{slug}/campaigns/{campaign_id}/edit")
async def campaign_update(
    request: Request,
    slug: str,
    campaign_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    data = {
        "name": form.get("name", "").strip(),
        "description": form.get("description", "").strip() or None,
        "status": form.get("status", "draft").strip(),
    }
    await campaign_svc.update_campaign(db, campaign_id, **data)
    return RedirectResponse(f"/loc/{slug}/campaigns/{campaign_id}", status_code=303)


@router.post("/loc/{slug}/campaigns/{campaign_id}/delete")
async def campaign_delete(
    slug: str,
    campaign_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    await campaign_svc.delete_campaign(db, campaign_id)
    return RedirectResponse(f"/loc/{slug}/campaigns/", status_code=303)


@router.post("/loc/{slug}/campaigns/{campaign_id}/steps")
async def add_step(
    request: Request,
    slug: str,
    campaign_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    data = {
        "step_type": form.get("step_type", "email").strip(),
        "subject": form.get("subject", "").strip() or None,
        "body": form.get("body", "").strip() or None,
        "delay_minutes": int(form.get("delay_minutes", "0")),
    }
    await campaign_svc.add_step(db, campaign_id, **data)
    return RedirectResponse(f"/loc/{slug}/campaigns/{campaign_id}", status_code=303)


@router.post("/loc/{slug}/campaigns/{campaign_id}/steps/{step_id}/delete")
async def delete_step(
    slug: str,
    campaign_id: uuid.UUID,
    step_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    await campaign_svc.delete_step(db, step_id)
    return RedirectResponse(f"/loc/{slug}/campaigns/{campaign_id}", status_code=303)


@router.post("/loc/{slug}/campaigns/{campaign_id}/enroll")
async def enroll_contact(
    request: Request,
    slug: str,
    campaign_id: uuid.UUID,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    contact_id = form.get("contact_id", "").strip()
    if contact_id:
        await campaign_svc.enroll_contact(db, location.id, campaign_id, uuid.UUID(contact_id))
    return RedirectResponse(f"/loc/{slug}/campaigns/{campaign_id}?tab=enrollments", status_code=303)


@router.post("/loc/{slug}/campaigns/{campaign_id}/enrollments/{enrollment_id}/remove")
async def unenroll_contact(
    slug: str,
    campaign_id: uuid.UUID,
    enrollment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    await campaign_svc.unenroll_contact(db, enrollment_id)
    return RedirectResponse(f"/loc/{slug}/campaigns/{campaign_id}?tab=enrollments", status_code=303)


@router.post("/loc/{slug}/campaigns/{campaign_id}/trigger-all")
async def trigger_all(
    request: Request,
    slug: str,
    campaign_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await campaign_svc.trigger_next_step(db, campaign_id)
    return RedirectResponse(f"/loc/{slug}/campaigns/{campaign_id}?tab=enrollments", status_code=303)
