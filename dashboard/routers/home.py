"""Home page router — landing page with app cards, metrics, and activity feed."""

from __future__ import annotations

from fastapi import APIRouter, Request

from ..app import templates
from ..services.metrics_svc import get_metrics
from ..services.activity_svc import get_recent_activity

router = APIRouter()


@router.get("/")
async def home(request: Request):
    metrics = await get_metrics()
    activity = await get_recent_activity(limit=30)
    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "metrics": metrics,
            "activity": activity,
        },
    )
