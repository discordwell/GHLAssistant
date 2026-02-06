"""Position management routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from ..config import settings
from ..database import get_db
from ..models import Candidate, Position, ScoringRubric

router = APIRouter()
templates = Jinja2Templates(directory=str(settings.templates_dir))


@router.get("/")
async def list_positions(request: Request, db: Session = Depends(get_db)):
    positions = db.exec(select(Position).order_by(Position.created_at.desc())).all()

    # Get candidate counts per position
    counts: dict[int, int] = {}
    for pos in positions:
        count = len(db.exec(
            select(Candidate).where(Candidate.position_id == pos.id, Candidate.status == "active")
        ).all())
        counts[pos.id] = count

    return templates.TemplateResponse("positions/list.html", {
        "request": request,
        "positions": positions,
        "counts": counts,
    })


@router.get("/new")
async def new_position(request: Request):
    return templates.TemplateResponse("positions/form.html", {
        "request": request,
        "position": None,
        "rubrics": [],
    })


@router.post("/new")
async def create_position(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    position = Position(
        title=form["title"],
        department=form.get("department") or None,
        description=form.get("description") or None,
        salary_min=float(form["salary_min"]) if form.get("salary_min") else None,
        salary_max=float(form["salary_max"]) if form.get("salary_max") else None,
        status=form.get("status", "open"),
    )
    db.add(position)
    db.commit()
    db.refresh(position)

    # Parse rubric criteria from the form (dynamic rows)
    idx = 0
    while f"rubric_criteria_{idx}" in form:
        criteria = form[f"rubric_criteria_{idx}"]
        weight = float(form.get(f"rubric_weight_{idx}", "1.0"))
        max_pts = int(form.get(f"rubric_max_{idx}", "10"))
        if criteria.strip():
            rubric = ScoringRubric(
                position_id=position.id,
                criteria=criteria.strip(),
                weight=weight,
                max_points=max_pts,
            )
            db.add(rubric)
        idx += 1
    db.commit()

    return RedirectResponse("/positions/", status_code=303)


@router.get("/{position_id}/edit")
async def edit_position(
    request: Request,
    position_id: int,
    db: Session = Depends(get_db),
):
    position = db.get(Position, position_id)
    if not position:
        return RedirectResponse("/positions/", status_code=303)

    rubrics = db.exec(
        select(ScoringRubric).where(ScoringRubric.position_id == position_id)
    ).all()

    return templates.TemplateResponse("positions/form.html", {
        "request": request,
        "position": position,
        "rubrics": rubrics,
    })


@router.post("/{position_id}/edit")
async def update_position(
    request: Request,
    position_id: int,
    db: Session = Depends(get_db),
):
    position = db.get(Position, position_id)
    if not position:
        return RedirectResponse("/positions/", status_code=303)

    form = await request.form()
    position.title = form["title"]
    position.department = form.get("department") or None
    position.description = form.get("description") or None
    position.salary_min = float(form["salary_min"]) if form.get("salary_min") else None
    position.salary_max = float(form["salary_max"]) if form.get("salary_max") else None
    position.status = form.get("status", position.status)

    # Replace rubrics
    old_rubrics = db.exec(
        select(ScoringRubric).where(ScoringRubric.position_id == position_id)
    ).all()
    for r in old_rubrics:
        db.delete(r)

    idx = 0
    while f"rubric_criteria_{idx}" in form:
        criteria = form[f"rubric_criteria_{idx}"]
        weight = float(form.get(f"rubric_weight_{idx}", "1.0"))
        max_pts = int(form.get(f"rubric_max_{idx}", "10"))
        if criteria.strip():
            rubric = ScoringRubric(
                position_id=position.id,
                criteria=criteria.strip(),
                weight=weight,
                max_points=max_pts,
            )
            db.add(rubric)
        idx += 1

    db.commit()
    return RedirectResponse("/positions/", status_code=303)
