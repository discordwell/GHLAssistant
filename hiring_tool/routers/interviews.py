"""Interview feedback routes."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from ..config import settings
from ..database import get_db
from ..models import Candidate, CandidateActivity, InterviewFeedback

router = APIRouter()
templates = Jinja2Templates(directory=str(settings.templates_dir))

INTERVIEW_TYPES = ["phone", "technical", "behavioral", "panel"]
RECOMMENDATIONS = ["strong_hire", "hire", "neutral", "no_hire", "strong_no_hire"]


@router.get("/new/{candidate_id}")
async def new_interview(
    request: Request,
    candidate_id: int,
    db: Session = Depends(get_db),
):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        return RedirectResponse("/candidates/", status_code=303)

    return templates.TemplateResponse("partials/interview_form.html", {
        "request": request,
        "candidate": candidate,
        "interview": None,
        "interview_types": INTERVIEW_TYPES,
        "recommendations": RECOMMENDATIONS,
    })


@router.post("/new/{candidate_id}")
async def create_interview(
    request: Request,
    candidate_id: int,
    db: Session = Depends(get_db),
):
    form = await request.form()

    feedback = InterviewFeedback(
        candidate_id=candidate_id,
        interviewer_name=form["interviewer_name"],
        interview_type=form.get("interview_type", "phone"),
        interview_date=datetime.fromisoformat(form["interview_date"]) if form.get("interview_date") else datetime.utcnow(),
        rating=int(form["rating"]),
        strengths=form.get("strengths") or None,
        concerns=form.get("concerns") or None,
        recommendation=form["recommendation"],
        notes=form.get("notes") or None,
    )
    db.add(feedback)

    activity = CandidateActivity(
        candidate_id=candidate_id,
        activity_type="interview",
        description=f"{feedback.interview_type.title()} interview by {feedback.interviewer_name}: {feedback.recommendation.replace('_', ' ')} (rating: {feedback.rating}/5)",
        created_by=feedback.interviewer_name,
    )
    db.add(activity)
    db.commit()

    return RedirectResponse(f"/candidates/{candidate_id}", status_code=303)
