"""Hiring analytics routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from ..config import settings
from ..database import get_db
from ..services.analytics_svc import compute_analytics

router = APIRouter()
templates = Jinja2Templates(directory=str(settings.templates_dir))


@router.get("/")
async def analytics_dashboard(request: Request, db: Session = Depends(get_db)):
    metrics = compute_analytics(db)
    return templates.TemplateResponse("analytics.html", {
        "request": request,
        "metrics": metrics,
    })
