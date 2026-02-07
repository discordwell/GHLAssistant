"""GHL Forms routes - list forms and view submissions (read-only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..models.location import Location
from ..services.ghl_svc import GHLNotLinkedError, fetch_forms, fetch_form_submissions
from ..tenant.deps import get_current_location

router = APIRouter(tags=["ghl-forms"])
templates = Jinja2Templates(directory=str(settings.templates_dir))


async def _all_locations(db: AsyncSession):
    return list((await db.execute(select(Location).order_by(Location.name))).scalars().all())


@router.get("/loc/{slug}/forms/")
async def form_list(
    request: Request,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    ghl_error = None
    forms = []
    if not location.ghl_location_id:
        ghl_error = "No GHL location linked. Go to Sync to connect."
    else:
        try:
            data = await fetch_forms(location.ghl_location_id)
            forms = data.get("forms", [])
        except GHLNotLinkedError as e:
            ghl_error = str(e)
        except Exception as e:
            ghl_error = f"Failed to load forms: {e}"

    return templates.TemplateResponse("ghl_forms/list.html", {
        "request": request,
        "location": location,
        "locations": await _all_locations(db),
        "forms": forms,
        "ghl_error": ghl_error,
    })


@router.get("/loc/{slug}/forms/{form_id}/submissions")
async def form_submissions(
    request: Request,
    form_id: str,
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
            data = await fetch_form_submissions(form_id, location.ghl_location_id, page=page)
            submissions = data.get("submissions", [])
            total = data.get("meta", {}).get("total", 0)
        except GHLNotLinkedError as e:
            ghl_error = str(e)
        except Exception as e:
            ghl_error = f"Failed to load submissions: {e}"

    return templates.TemplateResponse("ghl_forms/list.html", {
        "request": request,
        "location": location,
        "locations": await _all_locations(db),
        "forms": [],
        "submissions": submissions,
        "total_submissions": total,
        "selected_form_id": form_id,
        "page": page,
        "ghl_error": ghl_error,
    })
