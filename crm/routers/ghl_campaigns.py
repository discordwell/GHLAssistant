"""GHL Campaigns routes - list campaigns and view details (read-only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..models.location import Location
from ..services.ghl_svc import GHLNotLinkedError, fetch_campaigns, fetch_campaign
from ..tenant.deps import get_current_location

router = APIRouter(tags=["ghl-campaigns"])
templates = Jinja2Templates(directory=str(settings.templates_dir))


async def _all_locations(db: AsyncSession):
    return list((await db.execute(select(Location).order_by(Location.name))).scalars().all())


@router.get("/loc/{slug}/campaigns/")
async def campaign_list(
    request: Request,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    ghl_error = None
    campaigns = []
    if not location.ghl_location_id:
        ghl_error = "No GHL location linked. Go to Sync to connect."
    else:
        try:
            data = await fetch_campaigns(location.ghl_location_id)
            campaigns = data.get("campaigns", [])
        except GHLNotLinkedError as e:
            ghl_error = str(e)
        except Exception as e:
            ghl_error = f"Failed to load campaigns: {e}"

    return templates.TemplateResponse("ghl_campaigns/list.html", {
        "request": request,
        "location": location,
        "locations": await _all_locations(db),
        "campaigns": campaigns,
        "ghl_error": ghl_error,
    })


@router.get("/loc/{slug}/campaigns/{campaign_id}")
async def campaign_detail(
    request: Request,
    campaign_id: str,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    ghl_error = None
    campaign = None
    if not location.ghl_location_id:
        ghl_error = "No GHL location linked."
    else:
        try:
            data = await fetch_campaign(campaign_id)
            campaign = data.get("campaign", data)
        except GHLNotLinkedError as e:
            ghl_error = str(e)
        except Exception as e:
            ghl_error = f"Failed to load campaign: {e}"

    return templates.TemplateResponse("ghl_campaigns/list.html", {
        "request": request,
        "location": location,
        "locations": await _all_locations(db),
        "campaigns": [],
        "campaign_detail": campaign,
        "ghl_error": ghl_error,
    })
