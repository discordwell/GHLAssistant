"""Form routes - CRUD forms, fields, public submission."""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..models.location import Location
from ..services import form_svc
from ..tenant.deps import get_current_location

router = APIRouter(tags=["forms"])
templates = Jinja2Templates(directory=str(settings.templates_dir))


async def _all_locations(db: AsyncSession):
    return list((await db.execute(select(Location).order_by(Location.name))).scalars().all())


@router.get("/loc/{slug}/forms/")
async def form_list(
    request: Request,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    forms = await form_svc.list_forms(db, location.id)
    return templates.TemplateResponse("forms/list.html", {
        "request": request,
        "location": location,
        "locations": await _all_locations(db),
        "forms": forms,
    })


@router.get("/loc/{slug}/forms/new")
async def form_create_page(
    request: Request,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    return templates.TemplateResponse("forms/form.html", {
        "request": request,
        "location": location,
        "locations": await _all_locations(db),
        "form_obj": None,
    })


@router.post("/loc/{slug}/forms/")
async def form_create(
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
    f = await form_svc.create_form(db, location.id, **data)
    return RedirectResponse(f"/loc/{slug}/forms/{f.id}", status_code=303)


@router.get("/loc/{slug}/forms/{form_id}")
async def form_detail(
    request: Request,
    form_id: uuid.UUID,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
    tab: str = "fields",
):
    form_obj = await form_svc.get_form(db, form_id)
    if not form_obj or form_obj.location_id != location.id:
        return RedirectResponse(f"/loc/{location.slug}/forms/", status_code=303)
    submissions, sub_total = await form_svc.list_submissions(db, form_id)
    return templates.TemplateResponse("forms/detail.html", {
        "request": request,
        "location": location,
        "locations": await _all_locations(db),
        "form_obj": form_obj,
        "submissions": submissions,
        "sub_total": sub_total,
        "tab": tab,
        "field_types": ["text", "email", "phone", "textarea", "select", "checkbox", "number", "date"],
    })


@router.post("/loc/{slug}/forms/{form_id}/edit")
async def form_update(
    request: Request,
    slug: str,
    form_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    data = {
        "name": form.get("name", "").strip(),
        "description": form.get("description", "").strip() or None,
        "is_active": form.get("is_active") == "on",
    }
    await form_svc.update_form(db, form_id, **data)
    return RedirectResponse(f"/loc/{slug}/forms/{form_id}", status_code=303)


@router.post("/loc/{slug}/forms/{form_id}/delete")
async def form_delete(
    slug: str,
    form_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    await form_svc.delete_form(db, form_id)
    return RedirectResponse(f"/loc/{slug}/forms/", status_code=303)


@router.post("/loc/{slug}/forms/{form_id}/fields")
async def add_field(
    request: Request,
    slug: str,
    form_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    options = form.get("options", "").strip()
    options_json = None
    if options:
        options_json = {"choices": [o.strip() for o in options.split(",") if o.strip()]}
    data = {
        "label": form.get("label", "").strip(),
        "field_type": form.get("field_type", "text").strip(),
        "is_required": form.get("is_required") == "on",
        "placeholder": form.get("placeholder", "").strip() or None,
        "options_json": options_json,
    }
    await form_svc.add_field(db, form_id, **data)
    return RedirectResponse(f"/loc/{slug}/forms/{form_id}", status_code=303)


@router.post("/loc/{slug}/forms/{form_id}/fields/{field_id}/delete")
async def delete_field(
    slug: str,
    form_id: uuid.UUID,
    field_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    await form_svc.delete_field(db, field_id)
    return RedirectResponse(f"/loc/{slug}/forms/{form_id}", status_code=303)


@router.post("/loc/{slug}/forms/{form_id}/fields/reorder")
async def reorder_fields(
    request: Request,
    form_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    order = form.get("order", "")
    if order:
        ids = [i.strip() for i in order.split(",") if i.strip()]
        await form_svc.reorder_fields(db, form_id, ids)
    return HTMLResponse("")


# Public form endpoints (no auth, no base.html)
@router.get("/f/{form_id}")
async def public_form(
    request: Request,
    form_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    form_obj = await form_svc.get_form(db, form_id)
    if not form_obj or not form_obj.is_active:
        return HTMLResponse("<h1>Form not found</h1>", status_code=404)
    return templates.TemplateResponse("forms/public.html", {
        "request": request,
        "form_obj": form_obj,
    })


@router.post("/f/{form_id}")
async def public_form_submit(
    request: Request,
    form_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    form_obj = await form_svc.get_form(db, form_id)
    if not form_obj or not form_obj.is_active:
        return HTMLResponse("<h1>Form not found</h1>", status_code=404)

    form = await request.form()
    data = {}
    for field in form_obj.fields:
        val = form.get(str(field.id), "").strip()
        if val:
            data[field.label] = val

    source_ip = request.client.host if request.client else None
    await form_svc.create_submission(db, form_obj.location_id, form_id, data, source_ip=source_ip)
    return templates.TemplateResponse("forms/public_thanks.html", {
        "request": request,
        "form_obj": form_obj,
    })
