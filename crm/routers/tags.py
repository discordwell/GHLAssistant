"""Tag management routes."""

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
from ..services import tag_svc
from ..tenant.deps import get_current_location

router = APIRouter(tags=["tags"])
templates = Jinja2Templates(directory=str(settings.templates_dir))


@router.get("/loc/{slug}/tags/")
async def tag_list(
    request: Request,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    tags = await tag_svc.list_tags(db, location.id)
    locations = list((await db.execute(select(Location).order_by(Location.name))).scalars().all())
    return templates.TemplateResponse("tags/list.html", {
        "request": request,
        "location": location,
        "locations": locations,
        "tags": tags,
    })


@router.post("/loc/{slug}/tags/")
async def tag_create(
    request: Request,
    slug: str,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    name = form.get("name", "").strip()
    if name:
        await tag_svc.create_tag(db, location.id, name)
    return RedirectResponse(f"/loc/{slug}/tags/", status_code=303)


@router.post("/loc/{slug}/tags/{tag_id}/delete")
async def tag_delete(
    slug: str,
    tag_id: uuid.UUID,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    # Verify tag belongs to this location
    from ..models.tag import Tag
    stmt = select(Tag).where(Tag.id == tag_id, Tag.location_id == location.id)
    tag = (await db.execute(stmt)).scalar_one_or_none()
    if tag:
        await tag_svc.delete_tag(db, tag_id)
    return RedirectResponse(f"/loc/{slug}/tags/", status_code=303)
