"""Kanban board routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from ..config import settings
from ..database import get_db
from ..models import Candidate, CandidateActivity, Position

router = APIRouter(tags=["board"])
templates = Jinja2Templates(directory=str(settings.templates_dir))

# Stages that appear as columns on the board (exclude terminal states from columns)
BOARD_STAGES = [s for s in settings.stages if s not in ("Hired", "Rejected")]


@router.get("/board")
async def board(
    request: Request,
    position_id: int | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(Candidate).where(Candidate.status == "active")
    if position_id:
        stmt = stmt.where(Candidate.position_id == position_id)

    candidates = db.exec(stmt).all()

    # Group candidates by stage
    columns: dict[str, list[Candidate]] = {stage: [] for stage in BOARD_STAGES}
    for c in candidates:
        if c.stage in columns:
            columns[c.stage].append(c)

    # Sort each column by score descending (nulls last)
    for stage in columns:
        columns[stage].sort(key=lambda c: (c.score is not None, c.score or 0), reverse=True)

    positions = db.exec(select(Position)).all()
    position_map = {p.id: p.title for p in positions}
    open_positions = [p for p in positions if p.status == "open"]

    return templates.TemplateResponse("board.html", {
        "request": request,
        "columns": columns,
        "stages": BOARD_STAGES,
        "positions": open_positions,
        "position_map": position_map,
        "selected_position_id": position_id,
    })


@router.post("/board/move/{candidate_id}")
async def move_candidate(
    request: Request,
    candidate_id: int,
    db: Session = Depends(get_db),
):
    form = await request.form()
    new_stage = form.get("stage", "")

    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        return templates.TemplateResponse("partials/candidate_card.html", {
            "request": request, "candidate": None,
        })

    old_stage = candidate.stage
    if old_stage != new_stage and new_stage in settings.stages:
        candidate.stage = new_stage
        activity = CandidateActivity(
            candidate_id=candidate.id,
            activity_type="stage_change",
            description=f"Moved from {old_stage} to {new_stage}",
            created_by="user",
        )
        db.add(activity)
        db.commit()
        db.refresh(candidate)

    positions = db.exec(select(Position)).all()
    position_map = {p.id: p.title for p in positions}

    return templates.TemplateResponse("partials/candidate_card.html", {
        "request": request, "candidate": candidate, "position_map": position_map,
    })


@router.get("/board/column/{stage}")
async def board_column(
    request: Request,
    stage: str,
    position_id: int | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(Candidate).where(
        Candidate.status == "active",
        Candidate.stage == stage,
    )
    if position_id:
        stmt = stmt.where(Candidate.position_id == position_id)

    candidates = db.exec(stmt).all()
    candidates.sort(key=lambda c: (c.score is not None, c.score or 0), reverse=True)

    positions = db.exec(select(Position)).all()
    position_map = {p.id: p.title for p in positions}

    return templates.TemplateResponse("partials/kanban_column.html", {
        "request": request,
        "stage": stage,
        "candidates": candidates,
        "position_map": position_map,
    })
