"""GHL Funnels routes - list funnels and view pages (read-only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..models.location import Location
from ..services.ghl_svc import GHLNotLinkedError, fetch_funnels, fetch_funnel_pages
from ..tenant.deps import get_current_location

router = APIRouter(tags=["ghl-funnels"])
templates = Jinja2Templates(directory=str(settings.templates_dir))


async def _all_locations(db: AsyncSession):
    return list((await db.execute(select(Location).order_by(Location.name))).scalars().all())


@router.get("/loc/{slug}/funnels/")
async def funnel_list(
    request: Request,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    ghl_error = None
    funnels = []
    if not location.ghl_location_id:
        ghl_error = "No GHL location linked. Go to Sync to connect."
    else:
        try:
            data = await fetch_funnels(location.ghl_location_id)
            funnels = data.get("funnels", [])
        except GHLNotLinkedError as e:
            ghl_error = str(e)
        except Exception as e:
            ghl_error = f"Failed to load funnels: {e}"

    return templates.TemplateResponse("ghl_funnels/list.html", {
        "request": request,
        "location": location,
        "locations": await _all_locations(db),
        "funnels": funnels,
        "ghl_error": ghl_error,
    })


@router.get("/loc/{slug}/funnels/{funnel_id}/pages")
async def funnel_pages(
    request: Request,
    funnel_id: str,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    ghl_error = None
    pages = []
    if not location.ghl_location_id:
        ghl_error = "No GHL location linked."
    else:
        try:
            data = await fetch_funnel_pages(funnel_id, location.ghl_location_id)
            pages = data.get("pages", [])
        except GHLNotLinkedError as e:
            ghl_error = str(e)
        except Exception as e:
            ghl_error = f"Failed to load funnel pages: {e}"

    return templates.TemplateResponse("ghl_funnels/list.html", {
        "request": request,
        "location": location,
        "locations": await _all_locations(db),
        "funnels": [],
        "funnel_pages": pages,
        "selected_funnel_id": funnel_id,
        "ghl_error": ghl_error,
    })
