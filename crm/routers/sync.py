"""GHL sync routes - import/export UI."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..models.location import Location
from ..services import activity_svc
from ..tenant.deps import get_current_location

router = APIRouter(tags=["sync"])
templates = Jinja2Templates(directory=str(settings.templates_dir))


@router.get("/loc/{slug}/sync/")
async def sync_dashboard(
    request: Request,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    locations = list((await db.execute(select(Location).order_by(Location.name))).scalars().all())
    return templates.TemplateResponse("sync/dashboard.html", {
        "request": request,
        "location": location,
        "locations": locations,
        "has_ghl": bool(location.ghl_location_id),
    })


@router.post("/loc/{slug}/sync/import/preview")
async def import_preview(
    request: Request,
    slug: str,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    if not location.ghl_location_id:
        return RedirectResponse(f"/loc/{slug}/sync/", status_code=303)

    locations = list((await db.execute(select(Location).order_by(Location.name))).scalars().all())

    try:
        from ..sync.sync_engine import preview_import
        preview = await preview_import(location.ghl_location_id)
    except Exception as e:
        return templates.TemplateResponse("sync/dashboard.html", {
            "request": request,
            "location": location,
            "locations": locations,
            "has_ghl": True,
            "error": str(e),
        })

    return templates.TemplateResponse("sync/import_preview.html", {
        "request": request,
        "location": location,
        "locations": locations,
        "preview": preview,
    })


@router.post("/loc/{slug}/sync/import/confirm")
async def import_confirm(
    request: Request,
    slug: str,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    if not location.ghl_location_id:
        return RedirectResponse(f"/loc/{slug}/sync/", status_code=303)

    try:
        from ..sync.sync_engine import run_import
        result = await run_import(db, location)
    except Exception as e:
        locations = list((await db.execute(select(Location).order_by(Location.name))).scalars().all())
        return templates.TemplateResponse("sync/dashboard.html", {
            "request": request,
            "location": location,
            "locations": locations,
            "has_ghl": True,
            "error": str(e),
        })

    await activity_svc.log_activity(
        db, location.id, "sync", location.id, "import",
        description=f"Imported from GHL: {result.created} created, {result.updated} updated",
        metadata_json={"created": result.created, "updated": result.updated},
    )
    return RedirectResponse(f"/loc/{slug}/sync/", status_code=303)


@router.post("/loc/{slug}/sync/export")
async def export_to_ghl(
    request: Request,
    slug: str,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    if not location.ghl_location_id:
        return RedirectResponse(f"/loc/{slug}/sync/", status_code=303)

    try:
        from ..sync.sync_engine import run_export
        result = await run_export(db, location)
    except Exception as e:
        locations = list((await db.execute(select(Location).order_by(Location.name))).scalars().all())
        return templates.TemplateResponse("sync/dashboard.html", {
            "request": request,
            "location": location,
            "locations": locations,
            "has_ghl": True,
            "error": str(e),
        })

    await activity_svc.log_activity(
        db, location.id, "sync", location.id, "export",
        description=f"Exported to GHL: {result.created} created, {result.updated} updated",
        metadata_json={"created": result.created, "updated": result.updated},
    )
    return RedirectResponse(f"/loc/{slug}/sync/", status_code=303)
