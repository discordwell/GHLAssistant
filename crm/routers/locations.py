"""Location management routes."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..models.location import Location

router = APIRouter(tags=["locations"])
templates = Jinja2Templates(directory=str(settings.templates_dir))
templates.env.globals["app_urls"] = settings.app_urls


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return re.sub(r"-+", "-", slug).strip("-")


@router.get("/")
async def root(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Location).order_by(Location.name))
    locations = list(result.scalars().all())
    if len(locations) == 1:
        return RedirectResponse(f"/loc/{locations[0].slug}/")
    return templates.TemplateResponse("locations/list.html", {
        "request": request,
        "locations": locations,
    })


@router.get("/locations/")
async def location_list(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Location).order_by(Location.name))
    locations = list(result.scalars().all())
    return templates.TemplateResponse("locations/list.html", {
        "request": request,
        "locations": locations,
    })


@router.get("/locations/new")
async def location_form(request: Request):
    return templates.TemplateResponse("locations/form.html", {
        "request": request,
        "location": None,
    })


@router.post("/locations/")
async def location_create(request: Request, db: AsyncSession = Depends(get_db)):
    form = await request.form()
    name = form.get("name", "").strip()
    slug = _slugify(name)
    timezone = form.get("timezone", "UTC").strip()
    ghl_location_id = form.get("ghl_location_id", "").strip() or None
    ghl_company_id = form.get("ghl_company_id", "").strip() or None

    location = Location(
        name=name,
        slug=slug,
        timezone=timezone,
        ghl_location_id=ghl_location_id,
        ghl_company_id=ghl_company_id,
    )
    db.add(location)
    await db.commit()
    return RedirectResponse(f"/loc/{slug}/", status_code=303)


@router.get("/locations/{slug}/edit")
async def location_edit_form(
    request: Request, slug: str, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Location).where(Location.slug == slug))
    location = result.scalar_one_or_none()
    return templates.TemplateResponse("locations/form.html", {
        "request": request,
        "location": location,
    })


@router.post("/locations/{slug}/edit")
async def location_update(
    request: Request, slug: str, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Location).where(Location.slug == slug))
    location = result.scalar_one_or_none()
    if not location:
        return RedirectResponse("/locations/", status_code=303)

    form = await request.form()
    location.name = form.get("name", location.name).strip()
    location.timezone = form.get("timezone", location.timezone).strip()
    location.ghl_location_id = form.get("ghl_location_id", "").strip() or None
    location.ghl_company_id = form.get("ghl_company_id", "").strip() or None
    await db.commit()
    return RedirectResponse(f"/loc/{location.slug}/", status_code=303)
