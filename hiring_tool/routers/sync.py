"""GHL sync routes."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from ..config import settings
from ..database import get_db
from ..models import Candidate, CandidateActivity

router = APIRouter()
templates = Jinja2Templates(directory=str(settings.templates_dir))


@router.get("/")
async def sync_status(request: Request, db: Session = Depends(get_db)):
    synced = db.exec(
        select(Candidate).where(Candidate.ghl_contact_id.isnot(None))
    ).all()

    recent_syncs = db.exec(
        select(CandidateActivity)
        .where(CandidateActivity.activity_type == "synced")
        .order_by(CandidateActivity.created_at.desc())
    ).all()[:20]

    total_candidates = len(db.exec(select(Candidate)).all())

    return templates.TemplateResponse("sync.html", {
        "request": request,
        "synced_count": len(synced),
        "total_count": total_candidates,
        "recent_syncs": recent_syncs,
    })


@router.post("/push")
async def sync_push(request: Request, db: Session = Depends(get_db)):
    """Push local candidates to GHL."""
    from ..services.sync_engine import push_all_to_ghl

    results = await push_all_to_ghl(db)
    return templates.TemplateResponse("sync.html", {
        "request": request,
        "synced_count": results.get("synced", 0),
        "total_count": results.get("total", 0),
        "recent_syncs": [],
        "message": results.get("message", "Push complete"),
    })


@router.post("/pull")
async def sync_pull(request: Request, db: Session = Depends(get_db)):
    """Pull candidates from GHL."""
    from ..services.sync_engine import pull_from_ghl

    results = await pull_from_ghl(db)
    return templates.TemplateResponse("sync.html", {
        "request": request,
        "synced_count": results.get("synced", 0),
        "total_count": results.get("total", 0),
        "recent_syncs": [],
        "message": results.get("message", "Pull complete"),
    })
