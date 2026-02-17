"""Candidate CRUD routes."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from ..config import settings
from ..database import get_db
from ..models import (
    Candidate,
    CandidateActivity,
    CandidateScore,
    InterviewFeedback,
    Position,
    ScoringRubric,
)
from ..services.candidate_svc import compute_candidate_score

router = APIRouter()
templates = Jinja2Templates(directory=str(settings.templates_dir))
templates.env.globals["app_urls"] = settings.app_urls


@router.get("/")
async def list_candidates(
    request: Request,
    status: str | None = None,
    position_id: int | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(Candidate)
    if status:
        stmt = stmt.where(Candidate.status == status)
    if position_id:
        stmt = stmt.where(Candidate.position_id == position_id)

    candidates = db.exec(stmt).all()

    if search:
        q = search.lower()
        candidates = [
            c for c in candidates
            if q in (c.first_name or "").lower()
            or q in (c.last_name or "").lower()
            or q in (c.email or "").lower()
        ]

    positions = db.exec(select(Position)).all()

    return templates.TemplateResponse("candidates/list.html", {
        "request": request,
        "candidates": candidates,
        "positions": positions,
        "selected_status": status,
        "selected_position_id": position_id,
        "search": search or "",
    })


@router.get("/new")
async def new_candidate(request: Request, db: Session = Depends(get_db)):
    positions = db.exec(select(Position)).all()
    return templates.TemplateResponse("candidates/form.html", {
        "request": request,
        "candidate": None,
        "positions": positions,
        "stages": settings.stages,
    })


@router.post("/new")
async def create_candidate(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    candidate = Candidate(
        first_name=form["first_name"],
        last_name=form["last_name"],
        email=form.get("email") or None,
        phone=form.get("phone") or None,
        position_id=int(form["position_id"]) if form.get("position_id") else None,
        stage=form.get("stage", "Applied"),
        source=form.get("source") or None,
        resume_url=form.get("resume_url") or None,
        desired_salary=float(form["desired_salary"]) if form.get("desired_salary") else None,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    activity = CandidateActivity(
        candidate_id=candidate.id,
        activity_type="stage_change",
        description=f"Candidate added at stage: {candidate.stage}",
        created_by="user",
    )
    db.add(activity)
    db.commit()

    return RedirectResponse(f"/candidates/{candidate.id}", status_code=303)


@router.get("/{candidate_id}")
async def detail_candidate(
    request: Request,
    candidate_id: int,
    db: Session = Depends(get_db),
):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        return RedirectResponse("/candidates/", status_code=303)

    activities = db.exec(
        select(CandidateActivity)
        .where(CandidateActivity.candidate_id == candidate_id)
        .order_by(CandidateActivity.created_at.desc())
    ).all()

    feedbacks = db.exec(
        select(InterviewFeedback)
        .where(InterviewFeedback.candidate_id == candidate_id)
        .order_by(InterviewFeedback.interview_date.desc())
    ).all()

    scores = db.exec(
        select(CandidateScore)
        .where(CandidateScore.candidate_id == candidate_id)
    ).all()

    rubrics = {}
    for s in scores:
        rubric = db.get(ScoringRubric, s.rubric_id)
        if rubric:
            rubrics[s.rubric_id] = rubric

    position = db.get(Position, candidate.position_id) if candidate.position_id else None

    # Compute average rating from feedbacks
    avg_rating = None
    if feedbacks:
        avg_rating = sum(f.rating for f in feedbacks) / len(feedbacks)

    return templates.TemplateResponse("candidates/detail.html", {
        "request": request,
        "candidate": candidate,
        "activities": activities,
        "feedbacks": feedbacks,
        "scores": scores,
        "rubrics": rubrics,
        "position": position,
        "avg_rating": avg_rating,
        "stages": settings.stages,
    })


@router.get("/{candidate_id}/edit")
async def edit_candidate(
    request: Request,
    candidate_id: int,
    db: Session = Depends(get_db),
):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        return RedirectResponse("/candidates/", status_code=303)
    positions = db.exec(select(Position)).all()
    return templates.TemplateResponse("candidates/form.html", {
        "request": request,
        "candidate": candidate,
        "positions": positions,
        "stages": settings.stages,
    })


@router.post("/{candidate_id}/edit")
async def update_candidate(
    request: Request,
    candidate_id: int,
    db: Session = Depends(get_db),
):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        return RedirectResponse("/candidates/", status_code=303)

    form = await request.form()
    old_stage = candidate.stage

    candidate.first_name = form["first_name"]
    candidate.last_name = form["last_name"]
    candidate.email = form.get("email") or None
    candidate.phone = form.get("phone") or None
    candidate.position_id = int(form["position_id"]) if form.get("position_id") else None
    candidate.stage = form.get("stage", candidate.stage)
    candidate.source = form.get("source") or None
    candidate.resume_url = form.get("resume_url") or None
    candidate.desired_salary = float(form["desired_salary"]) if form.get("desired_salary") else None
    candidate.status = form.get("status", candidate.status)

    if candidate.stage != old_stage:
        activity = CandidateActivity(
            candidate_id=candidate.id,
            activity_type="stage_change",
            description=f"Moved from {old_stage} to {candidate.stage}",
            created_by="user",
        )
        db.add(activity)

    db.commit()
    return RedirectResponse(f"/candidates/{candidate_id}", status_code=303)


@router.post("/{candidate_id}/note")
async def add_note(
    request: Request,
    candidate_id: int,
    db: Session = Depends(get_db),
):
    form = await request.form()
    note_text = form.get("note", "").strip()
    if note_text:
        activity = CandidateActivity(
            candidate_id=candidate_id,
            activity_type="note",
            description=note_text,
            created_by=form.get("author", "user"),
        )
        db.add(activity)
        db.commit()

    activities = db.exec(
        select(CandidateActivity)
        .where(CandidateActivity.candidate_id == candidate_id)
        .order_by(CandidateActivity.created_at.desc())
    ).all()

    return templates.TemplateResponse("partials/timeline_entry.html", {
        "request": request,
        "activities": activities,
    })


@router.post("/{candidate_id}/score")
async def score_candidate(
    request: Request,
    candidate_id: int,
    db: Session = Depends(get_db),
):
    form = await request.form()
    rubric_id = int(form["rubric_id"])
    points = int(form["points"])
    notes = form.get("notes") or None

    existing = db.exec(
        select(CandidateScore).where(
            CandidateScore.candidate_id == candidate_id,
            CandidateScore.rubric_id == rubric_id,
        )
    ).first()

    if existing:
        existing.points = points
        existing.notes = notes
    else:
        score = CandidateScore(
            candidate_id=candidate_id,
            rubric_id=rubric_id,
            points=points,
            notes=notes,
        )
        db.add(score)

    db.commit()

    candidate = db.get(Candidate, candidate_id)
    if candidate:
        new_score = compute_candidate_score(db, candidate_id)
        candidate.score = new_score
        activity = CandidateActivity(
            candidate_id=candidate_id,
            activity_type="score_update",
            description=f"Score updated to {new_score:.0f}",
            created_by="user",
        )
        db.add(activity)
        db.commit()

    return templates.TemplateResponse("partials/score_badge.html", {
        "request": request,
        "score": candidate.score if candidate else None,
    })
