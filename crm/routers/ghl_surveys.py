"""GHL Surveys routes - list surveys and view submissions (read-only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..models.location import Location
from ..services.ghl_svc import GHLNotLinkedError, fetch_surveys, fetch_survey_submissions
from ..tenant.deps import get_current_location

router = APIRouter(tags=["ghl-surveys"])
templates = Jinja2Templates(directory=str(settings.templates_dir))


async def _all_locations(db: AsyncSession):
    return list((await db.execute(select(Location).order_by(Location.name))).scalars().all())


@router.get("/loc/{slug}/surveys/")
async def survey_list(
    request: Request,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    ghl_error = None
    surveys = []
    if not location.ghl_location_id:
        ghl_error = "No GHL location linked. Go to Sync to connect."
    else:
        try:
            data = await fetch_surveys(location.ghl_location_id)
            surveys = data.get("surveys", [])
        except GHLNotLinkedError as e:
            ghl_error = str(e)
        except Exception as e:
            ghl_error = f"Failed to load surveys: {e}"

    return templates.TemplateResponse("ghl_surveys/list.html", {
        "request": request,
        "location": location,
        "locations": await _all_locations(db),
        "surveys": surveys,
        "ghl_error": ghl_error,
    })


@router.get("/loc/{slug}/surveys/{survey_id}/submissions")
async def survey_submissions(
    request: Request,
    survey_id: str,
    page: int = 1,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    ghl_error = None
    submissions = []
    total = 0
    if not location.ghl_location_id:
        ghl_error = "No GHL location linked."
    else:
        try:
            data = await fetch_survey_submissions(survey_id, location.ghl_location_id, page=page)
            submissions = data.get("submissions", [])
            total = data.get("meta", {}).get("total", 0)
        except GHLNotLinkedError as e:
            ghl_error = str(e)
        except Exception as e:
            ghl_error = f"Failed to load submissions: {e}"

    return templates.TemplateResponse("ghl_surveys/list.html", {
        "request": request,
        "location": location,
        "locations": await _all_locations(db),
        "surveys": [],
        "submissions": submissions,
        "total_submissions": total,
        "selected_survey_id": survey_id,
        "page": page,
        "ghl_error": ghl_error,
    })
