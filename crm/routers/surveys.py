"""Survey routes - CRUD surveys, questions, public submission."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..models.location import Location
from ..services import survey_svc
from ..tenant.deps import get_current_location

router = APIRouter(tags=["surveys"])
templates = Jinja2Templates(directory=str(settings.templates_dir))
templates.env.globals["app_urls"] = settings.app_urls


async def _all_locations(db: AsyncSession):
    return list((await db.execute(select(Location).order_by(Location.name))).scalars().all())


@router.get("/loc/{slug}/surveys/")
async def survey_list(
    request: Request,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    surveys = await survey_svc.list_surveys(db, location.id)
    return templates.TemplateResponse("surveys/list.html", {
        "request": request,
        "location": location,
        "locations": await _all_locations(db),
        "surveys": surveys,
    })


@router.get("/loc/{slug}/surveys/new")
async def survey_create_page(
    request: Request,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    return templates.TemplateResponse("surveys/form.html", {
        "request": request,
        "location": location,
        "locations": await _all_locations(db),
        "survey": None,
    })


@router.post("/loc/{slug}/surveys/")
async def survey_create(
    request: Request,
    slug: str,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    data = {
        "name": form.get("name", "").strip(),
        "description": form.get("description", "").strip() or None,
    }
    s = await survey_svc.create_survey(db, location.id, **data)
    return RedirectResponse(f"/loc/{slug}/surveys/{s.id}", status_code=303)


@router.get("/loc/{slug}/surveys/{survey_id}")
async def survey_detail(
    request: Request,
    survey_id: uuid.UUID,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
    tab: str = "questions",
):
    survey = await survey_svc.get_survey(db, survey_id)
    if not survey or survey.location_id != location.id:
        return RedirectResponse(f"/loc/{location.slug}/surveys/", status_code=303)
    submissions, sub_total = await survey_svc.list_submissions(db, survey_id)
    return templates.TemplateResponse("surveys/detail.html", {
        "request": request,
        "location": location,
        "locations": await _all_locations(db),
        "survey": survey,
        "submissions": submissions,
        "sub_total": sub_total,
        "tab": tab,
        "question_types": ["text", "rating", "select", "multi_select", "yes_no", "long_text"],
    })


@router.post("/loc/{slug}/surveys/{survey_id}/edit")
async def survey_update(
    request: Request,
    slug: str,
    survey_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    data = {
        "name": form.get("name", "").strip(),
        "description": form.get("description", "").strip() or None,
        "is_active": form.get("is_active") == "on",
    }
    await survey_svc.update_survey(db, survey_id, **data)
    return RedirectResponse(f"/loc/{slug}/surveys/{survey_id}", status_code=303)


@router.post("/loc/{slug}/surveys/{survey_id}/delete")
async def survey_delete(
    slug: str,
    survey_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    await survey_svc.delete_survey(db, survey_id)
    return RedirectResponse(f"/loc/{slug}/surveys/", status_code=303)


@router.post("/loc/{slug}/surveys/{survey_id}/questions")
async def add_question(
    request: Request,
    slug: str,
    survey_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    options = form.get("options", "").strip()
    options_json = None
    if options:
        options_json = {"choices": [o.strip() for o in options.split(",") if o.strip()]}
    data = {
        "question_text": form.get("question_text", "").strip(),
        "question_type": form.get("question_type", "text").strip(),
        "is_required": form.get("is_required") == "on",
        "options_json": options_json,
    }
    await survey_svc.add_question(db, survey_id, **data)
    return RedirectResponse(f"/loc/{slug}/surveys/{survey_id}", status_code=303)


@router.post("/loc/{slug}/surveys/{survey_id}/questions/{question_id}/delete")
async def delete_question(
    slug: str,
    survey_id: uuid.UUID,
    question_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    await survey_svc.delete_question(db, question_id)
    return RedirectResponse(f"/loc/{slug}/surveys/{survey_id}", status_code=303)


@router.post("/loc/{slug}/surveys/{survey_id}/questions/reorder")
async def reorder_questions(
    request: Request,
    survey_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    order = form.get("order", "")
    if order:
        ids = [i.strip() for i in order.split(",") if i.strip()]
        await survey_svc.reorder_questions(db, survey_id, ids)
    return HTMLResponse("")


# Public survey endpoints
@router.get("/s/{survey_id}")
async def public_survey(
    request: Request,
    survey_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    survey = await survey_svc.get_survey(db, survey_id)
    if not survey or not survey.is_active:
        return HTMLResponse("<h1>Survey not found</h1>", status_code=404)
    return templates.TemplateResponse("surveys/public.html", {
        "request": request,
        "survey": survey,
    })


@router.post("/s/{survey_id}")
async def public_survey_submit(
    request: Request,
    survey_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    survey = await survey_svc.get_survey(db, survey_id)
    if not survey or not survey.is_active:
        return HTMLResponse("<h1>Survey not found</h1>", status_code=404)

    form = await request.form()
    answers = {}
    for q in survey.questions:
        val = form.get(str(q.id), "").strip()
        if val:
            answers[q.question_text] = val

    await survey_svc.create_submission(db, survey.location_id, survey_id, answers)
    return templates.TemplateResponse("surveys/public_thanks.html", {
        "request": request,
        "survey": survey,
    })
