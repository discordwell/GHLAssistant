"""Dashboard route - stats + recent activity."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..models.contact import Contact
from ..models.opportunity import Opportunity
from ..models.pipeline import Pipeline
from ..models.tag import Tag
from ..models.activity import Activity
from ..models.location import Location
from ..tenant.deps import get_current_location

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory=str(settings.templates_dir))


@router.get("/loc/{slug}/")
async def dashboard(
    request: Request,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    lid = location.id

    # Gather stats
    contact_count = (await db.execute(
        select(func.count()).where(Contact.location_id == lid)
    )).scalar() or 0

    pipeline_count = (await db.execute(
        select(func.count()).where(Pipeline.location_id == lid)
    )).scalar() or 0

    opp_count = (await db.execute(
        select(func.count()).where(Opportunity.location_id == lid)
    )).scalar() or 0

    tag_count = (await db.execute(
        select(func.count()).where(Tag.location_id == lid)
    )).scalar() or 0

    open_value = (await db.execute(
        select(func.coalesce(func.sum(Opportunity.monetary_value), 0)).where(
            Opportunity.location_id == lid, Opportunity.status == "open"
        )
    )).scalar() or 0

    # Recent activity
    activity_stmt = (
        select(Activity)
        .where(Activity.location_id == lid)
        .order_by(Activity.created_at.desc())
        .limit(20)
    )
    activities = list((await db.execute(activity_stmt)).scalars().all())

    # All locations for switcher
    all_locations = list(
        (await db.execute(select(Location).order_by(Location.name))).scalars().all()
    )

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "location": location,
        "locations": all_locations,
        "contact_count": contact_count,
        "pipeline_count": pipeline_count,
        "opp_count": opp_count,
        "tag_count": tag_count,
        "open_value": open_value,
        "activities": activities,
    })
