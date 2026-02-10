"""Funnel routes - CRUD funnels, pages, public page view."""

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
from ..services import funnel_svc
from ..tenant.deps import get_current_location

router = APIRouter(tags=["funnels"])
templates = Jinja2Templates(directory=str(settings.templates_dir))


async def _all_locations(db: AsyncSession):
    return list((await db.execute(select(Location).order_by(Location.name))).scalars().all())


@router.get("/loc/{slug}/funnels/")
async def funnel_list(
    request: Request,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    funnels = await funnel_svc.list_funnels(db, location.id)
    return templates.TemplateResponse("funnels/list.html", {
        "request": request,
        "location": location,
        "locations": await _all_locations(db),
        "funnels": funnels,
    })


@router.get("/loc/{slug}/funnels/new")
async def funnel_create_page(
    request: Request,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    return templates.TemplateResponse("funnels/form.html", {
        "request": request,
        "location": location,
        "locations": await _all_locations(db),
        "funnel": None,
    })


@router.post("/loc/{slug}/funnels/")
async def funnel_create(
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
    f = await funnel_svc.create_funnel(db, location.id, **data)
    return RedirectResponse(f"/loc/{slug}/funnels/{f.id}", status_code=303)


@router.get("/loc/{slug}/funnels/{funnel_id}")
async def funnel_detail(
    request: Request,
    funnel_id: uuid.UUID,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    funnel = await funnel_svc.get_funnel(db, funnel_id)
    if not funnel or funnel.location_id != location.id:
        return RedirectResponse(f"/loc/{location.slug}/funnels/", status_code=303)
    return templates.TemplateResponse("funnels/detail.html", {
        "request": request,
        "location": location,
        "locations": await _all_locations(db),
        "funnel": funnel,
    })


@router.post("/loc/{slug}/funnels/{funnel_id}/edit")
async def funnel_update(
    request: Request,
    slug: str,
    funnel_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    data = {
        "name": form.get("name", "").strip(),
        "description": form.get("description", "").strip() or None,
        "is_published": form.get("is_published") == "on",
    }
    await funnel_svc.update_funnel(db, funnel_id, **data)
    return RedirectResponse(f"/loc/{slug}/funnels/{funnel_id}", status_code=303)


@router.post("/loc/{slug}/funnels/{funnel_id}/delete")
async def funnel_delete(
    slug: str,
    funnel_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    await funnel_svc.delete_funnel(db, funnel_id)
    return RedirectResponse(f"/loc/{slug}/funnels/", status_code=303)


@router.post("/loc/{slug}/funnels/{funnel_id}/pages")
async def add_page(
    request: Request,
    slug: str,
    funnel_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    data = {
        "name": form.get("name", "").strip(),
        "url_slug": form.get("url_slug", "").strip(),
        "content_html": form.get("content_html", "").strip() or None,
        "is_published": form.get("is_published") == "on",
    }
    await funnel_svc.add_page(db, funnel_id, **data)
    return RedirectResponse(f"/loc/{slug}/funnels/{funnel_id}", status_code=303)


@router.post("/loc/{slug}/funnels/{funnel_id}/pages/{page_id}/edit")
async def edit_page(
    request: Request,
    slug: str,
    funnel_id: uuid.UUID,
    page_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    data = {
        "name": form.get("name", "").strip(),
        "url_slug": form.get("url_slug", "").strip(),
        "content_html": form.get("content_html", ""),
        "is_published": form.get("is_published") == "on",
    }
    await funnel_svc.update_page(db, page_id, **data)
    return RedirectResponse(f"/loc/{slug}/funnels/{funnel_id}", status_code=303)


@router.post("/loc/{slug}/funnels/{funnel_id}/pages/{page_id}/delete")
async def delete_page(
    slug: str,
    funnel_id: uuid.UUID,
    page_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    await funnel_svc.delete_page(db, page_id)
    return RedirectResponse(f"/loc/{slug}/funnels/{funnel_id}", status_code=303)


# Public funnel page
@router.get("/p/{funnel_id}/{url_slug:path}")
async def public_page(
    request: Request,
    funnel_id: uuid.UUID,
    url_slug: str,
    db: AsyncSession = Depends(get_db),
):
    page = await funnel_svc.get_public_page(db, funnel_id, url_slug)
    if not page:
        return HTMLResponse("<h1>Page not found</h1>", status_code=404)
    return templates.TemplateResponse("funnels/public_page.html", {
        "request": request,
        "page": page,
    })
