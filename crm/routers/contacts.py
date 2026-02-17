"""Contact routes - list, detail, form, notes, tags."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..models.location import Location
from ..models.tag import Tag
from ..services import contact_svc, tag_svc, note_svc, activity_svc, custom_field_svc
from ..tenant.deps import get_current_location

router = APIRouter(tags=["contacts"])
templates = Jinja2Templates(directory=str(settings.templates_dir))
templates.env.globals["app_urls"] = settings.app_urls


async def _all_locations(db: AsyncSession):
    return list((await db.execute(select(Location).order_by(Location.name))).scalars().all())


@router.get("/loc/{slug}/contacts/")
async def contact_list(
    request: Request,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
    search: str | None = None,
    tag: str | None = None,
    page: int = 1,
):
    per_page = 50
    offset = (page - 1) * per_page
    contacts, total = await contact_svc.list_contacts(
        db, location.id, search=search, tag_name=tag, offset=offset, limit=per_page
    )
    tags = await tag_svc.list_tags(db, location.id)
    total_pages = max(1, (total + per_page - 1) // per_page)

    return templates.TemplateResponse("contacts/list.html", {
        "request": request,
        "location": location,
        "locations": await _all_locations(db),
        "contacts": contacts,
        "tags": tags,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "search": search or "",
        "current_tag": tag or "",
    })


@router.get("/loc/{slug}/contacts/new")
async def contact_form(
    request: Request,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    tags = await tag_svc.list_tags(db, location.id)
    return templates.TemplateResponse("contacts/form.html", {
        "request": request,
        "location": location,
        "locations": await _all_locations(db),
        "contact": None,
        "tags": tags,
    })


@router.post("/loc/{slug}/contacts/")
async def contact_create(
    request: Request,
    slug: str,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    data = {
        "first_name": form.get("first_name", "").strip() or None,
        "last_name": form.get("last_name", "").strip() or None,
        "email": form.get("email", "").strip() or None,
        "phone": form.get("phone", "").strip() or None,
        "company_name": form.get("company_name", "").strip() or None,
        "address1": form.get("address1", "").strip() or None,
        "city": form.get("city", "").strip() or None,
        "state": form.get("state", "").strip() or None,
        "postal_code": form.get("postal_code", "").strip() or None,
        "country": form.get("country", "").strip() or None,
        "source": form.get("source", "").strip() or None,
        "dnd": form.get("dnd") == "on",
    }
    contact = await contact_svc.create_contact(db, location.id, **data)
    await activity_svc.log_activity(
        db, location.id, "contact", contact.id, "created",
        description=f"Contact {contact.full_name} created"
    )
    return RedirectResponse(f"/loc/{slug}/contacts/{contact.id}", status_code=303)


@router.get("/loc/{slug}/contacts/{contact_id}")
async def contact_detail(
    request: Request,
    contact_id: uuid.UUID,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
    tab: str = "notes",
):
    contact = await contact_svc.get_contact(db, contact_id)
    if not contact or contact.location_id != location.id:
        return RedirectResponse(f"/loc/{location.slug}/contacts/", status_code=303)

    all_tags = await tag_svc.list_tags(db, location.id)
    activities = await activity_svc.list_activities(
        db, location.id, entity_type="contact", entity_id=contact_id, limit=20
    )
    custom_defs = await custom_field_svc.list_definitions(db, location.id, "contact")
    custom_vals = await custom_field_svc.get_values_for_entity(db, contact_id, "contact")

    return templates.TemplateResponse("contacts/detail.html", {
        "request": request,
        "location": location,
        "locations": await _all_locations(db),
        "contact": contact,
        "all_tags": all_tags,
        "activities": activities,
        "custom_defs": custom_defs,
        "custom_vals": custom_vals,
        "tab": tab,
    })


@router.get("/loc/{slug}/contacts/{contact_id}/edit")
async def contact_edit_form(
    request: Request,
    contact_id: uuid.UUID,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    contact = await contact_svc.get_contact(db, contact_id)
    if not contact or contact.location_id != location.id:
        return RedirectResponse(f"/loc/{location.slug}/contacts/", status_code=303)
    tags = await tag_svc.list_tags(db, location.id)
    return templates.TemplateResponse("contacts/form.html", {
        "request": request,
        "location": location,
        "locations": await _all_locations(db),
        "contact": contact,
        "tags": tags,
    })


@router.post("/loc/{slug}/contacts/{contact_id}/edit")
async def contact_update(
    request: Request,
    slug: str,
    contact_id: uuid.UUID,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    data = {
        "first_name": form.get("first_name", "").strip() or None,
        "last_name": form.get("last_name", "").strip() or None,
        "email": form.get("email", "").strip() or None,
        "phone": form.get("phone", "").strip() or None,
        "company_name": form.get("company_name", "").strip() or None,
        "address1": form.get("address1", "").strip() or None,
        "city": form.get("city", "").strip() or None,
        "state": form.get("state", "").strip() or None,
        "postal_code": form.get("postal_code", "").strip() or None,
        "country": form.get("country", "").strip() or None,
        "source": form.get("source", "").strip() or None,
        "dnd": form.get("dnd") == "on",
    }
    await contact_svc.update_contact(db, contact_id, **data)
    await activity_svc.log_activity(
        db, location.id, "contact", contact_id, "updated",
        description="Contact updated"
    )
    return RedirectResponse(f"/loc/{slug}/contacts/{contact_id}", status_code=303)


@router.post("/loc/{slug}/contacts/{contact_id}/delete")
async def contact_delete(
    slug: str,
    contact_id: uuid.UUID,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    await contact_svc.delete_contact(db, contact_id)
    return RedirectResponse(f"/loc/{slug}/contacts/", status_code=303)


@router.post("/loc/{slug}/contacts/{contact_id}/notes")
async def add_note(
    request: Request,
    slug: str,
    contact_id: uuid.UUID,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    body = form.get("body", "").strip()
    if body:
        await note_svc.create_note(db, location.id, contact_id, body, created_by="user")
        await activity_svc.log_activity(
            db, location.id, "contact", contact_id, "note_added",
            description="Note added"
        )
    return RedirectResponse(f"/loc/{slug}/contacts/{contact_id}?tab=notes", status_code=303)


@router.post("/loc/{slug}/contacts/{contact_id}/tags/{tag_id}")
async def add_tag(
    request: Request,
    slug: str,
    contact_id: uuid.UUID,
    tag_id: uuid.UUID,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    await contact_svc.add_tag_to_contact(db, contact_id, tag_id)
    return RedirectResponse(f"/loc/{slug}/contacts/{contact_id}", status_code=303)


@router.post("/loc/{slug}/contacts/{contact_id}/tags/{tag_id}/remove")
async def remove_tag(
    slug: str,
    contact_id: uuid.UUID,
    tag_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    await contact_svc.remove_tag_from_contact(db, contact_id, tag_id)
    return RedirectResponse(f"/loc/{slug}/contacts/{contact_id}", status_code=303)
