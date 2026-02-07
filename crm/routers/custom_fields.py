"""Custom field definition routes."""

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
from ..services import custom_field_svc
from ..tenant.deps import get_current_location

router = APIRouter(tags=["custom_fields"])
templates = Jinja2Templates(directory=str(settings.templates_dir))


@router.get("/loc/{slug}/custom-fields/")
async def custom_field_list(
    request: Request,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    definitions = await custom_field_svc.list_definitions(db, location.id)
    locations = list((await db.execute(select(Location).order_by(Location.name))).scalars().all())
    return templates.TemplateResponse("custom_fields/list.html", {
        "request": request,
        "location": location,
        "locations": locations,
        "definitions": definitions,
    })


@router.post("/loc/{slug}/custom-fields/")
async def custom_field_create(
    request: Request,
    slug: str,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    name = form.get("name", "").strip()
    field_key = form.get("field_key", "").strip()
    data_type = form.get("data_type", "text")
    entity_type = form.get("entity_type", "contact")

    if name and field_key:
        await custom_field_svc.create_definition(
            db, location.id,
            name=name, field_key=field_key, data_type=data_type, entity_type=entity_type
        )
    return RedirectResponse(f"/loc/{slug}/custom-fields/", status_code=303)


@router.post("/loc/{slug}/custom-fields/{defn_id}/delete")
async def custom_field_delete(
    slug: str,
    defn_id: uuid.UUID,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    # Verify definition belongs to this location
    from ..models.custom_field import CustomFieldDefinition
    stmt = select(CustomFieldDefinition).where(
        CustomFieldDefinition.id == defn_id, CustomFieldDefinition.location_id == location.id
    )
    defn = (await db.execute(stmt)).scalar_one_or_none()
    if defn:
        await custom_field_svc.delete_definition(db, defn_id)
    return RedirectResponse(f"/loc/{slug}/custom-fields/", status_code=303)
