"""Pipeline routes - list, kanban board, opportunity CRUD."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..config import settings
from ..database import get_db
from ..models.contact import Contact
from ..models.location import Location
from ..models.opportunity import Opportunity
from ..models.pipeline import Pipeline, PipelineStage
from ..services import pipeline_svc, contact_svc, activity_svc
from ..tenant.deps import get_current_location

router = APIRouter(tags=["pipelines"])
templates = Jinja2Templates(directory=str(settings.templates_dir))


async def _all_locations(db: AsyncSession):
    return list((await db.execute(select(Location).order_by(Location.name))).scalars().all())


@router.get("/loc/{slug}/pipelines/")
async def pipeline_list(
    request: Request,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    pipelines = await pipeline_svc.list_pipelines(db, location.id)
    return templates.TemplateResponse("pipelines/list.html", {
        "request": request,
        "location": location,
        "locations": await _all_locations(db),
        "pipelines": pipelines,
    })


@router.get("/loc/{slug}/pipelines/new")
async def pipeline_form(
    request: Request,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    return templates.TemplateResponse("pipelines/form.html", {
        "request": request,
        "location": location,
        "locations": await _all_locations(db),
        "pipeline": None,
    })


@router.post("/loc/{slug}/pipelines/")
async def pipeline_create(
    request: Request,
    slug: str,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    name = form.get("name", "").strip()
    description = form.get("description", "").strip() or None
    stages_raw = form.get("stages", "").strip()

    pipeline = await pipeline_svc.create_pipeline(db, location.id, name, description)

    # Create stages from comma-separated list
    if stages_raw:
        for i, stage_name in enumerate(stages_raw.split(",")):
            stage_name = stage_name.strip()
            if stage_name:
                await pipeline_svc.add_stage(db, pipeline.id, stage_name, position=i)

    await activity_svc.log_activity(
        db, location.id, "pipeline", pipeline.id, "created",
        description=f"Pipeline '{name}' created"
    )
    return RedirectResponse(f"/loc/{slug}/pipelines/{pipeline.id}", status_code=303)


@router.get("/loc/{slug}/pipelines/{pipeline_id}")
async def pipeline_board(
    request: Request,
    pipeline_id: uuid.UUID,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    pipeline = await pipeline_svc.get_pipeline(db, pipeline_id)
    if not pipeline or pipeline.location_id != location.id:
        return RedirectResponse(f"/loc/{location.slug}/pipelines/", status_code=303)

    # Group opportunities by stage
    opps = await pipeline_svc.list_opportunities(db, pipeline_id)
    columns: dict[uuid.UUID, list[Opportunity]] = {}
    for stage in pipeline.stages:
        columns[stage.id] = []
    for opp in opps:
        if opp.stage_id and opp.stage_id in columns:
            columns[opp.stage_id].append(opp)

    # Get contacts for opportunity form
    contacts_list, _ = await contact_svc.list_contacts(db, location.id, limit=500)

    return templates.TemplateResponse("pipelines/board.html", {
        "request": request,
        "location": location,
        "locations": await _all_locations(db),
        "pipeline": pipeline,
        "columns": columns,
        "contacts": contacts_list,
    })


@router.post("/loc/{slug}/pipelines/{pipeline_id}/stages")
async def stage_add(
    request: Request,
    slug: str,
    pipeline_id: uuid.UUID,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    name = form.get("name", "").strip()
    if name:
        await pipeline_svc.add_stage(db, pipeline_id, name)
    return RedirectResponse(f"/loc/{slug}/pipelines/{pipeline_id}", status_code=303)


@router.post("/loc/{slug}/pipelines/{pipeline_id}/stages/{stage_id}/delete")
async def stage_delete(
    slug: str,
    pipeline_id: uuid.UUID,
    stage_id: uuid.UUID,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    # Verify stage belongs to a pipeline owned by this location
    stmt = (
        select(PipelineStage)
        .join(Pipeline)
        .where(PipelineStage.id == stage_id, Pipeline.location_id == location.id)
    )
    stage = (await db.execute(stmt)).scalar_one_or_none()
    if stage:
        await pipeline_svc.delete_stage(db, stage_id)
    return RedirectResponse(f"/loc/{slug}/pipelines/{pipeline_id}", status_code=303)


@router.post("/loc/{slug}/pipelines/{pipeline_id}/opportunities")
async def opportunity_create(
    request: Request,
    slug: str,
    pipeline_id: uuid.UUID,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    name = form.get("name", "").strip()
    stage_id_str = form.get("stage_id", "")
    contact_id_str = form.get("contact_id", "")
    monetary_value_str = form.get("monetary_value", "")
    source = form.get("source", "").strip() or None

    stage_id = uuid.UUID(stage_id_str) if stage_id_str else None
    contact_id = uuid.UUID(contact_id_str) if contact_id_str else None
    monetary_value = float(monetary_value_str) if monetary_value_str else None

    opp = await pipeline_svc.create_opportunity(
        db, location.id,
        name=name,
        pipeline_id=pipeline_id,
        stage_id=stage_id,
        contact_id=contact_id,
        monetary_value=monetary_value,
        source=source,
    )
    await activity_svc.log_activity(
        db, location.id, "opportunity", opp.id, "created",
        description=f"Opportunity '{name}' created"
    )
    return RedirectResponse(f"/loc/{slug}/pipelines/{pipeline_id}", status_code=303)


@router.get("/loc/{slug}/opportunities/{opp_id}")
async def opportunity_detail(
    request: Request,
    opp_id: uuid.UUID,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    opp = await pipeline_svc.get_opportunity(db, opp_id)
    if not opp or opp.location_id != location.id:
        return RedirectResponse(f"/loc/{location.slug}/pipelines/", status_code=303)

    activities = await activity_svc.list_activities(
        db, location.id, entity_type="opportunity", entity_id=opp_id, limit=20
    )
    return templates.TemplateResponse("opportunities/detail.html", {
        "request": request,
        "location": location,
        "locations": await _all_locations(db),
        "opp": opp,
        "activities": activities,
    })


@router.post("/loc/{slug}/opportunities/{opp_id}/move")
async def opportunity_move(
    request: Request,
    slug: str,
    opp_id: uuid.UUID,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    """Move opportunity to new stage (kanban drag)."""
    form = await request.form()
    stage_id_str = form.get("stage_id", "")
    if not stage_id_str:
        return {"ok": False}

    stage_id = uuid.UUID(stage_id_str)
    opp = await pipeline_svc.move_opportunity(db, opp_id, stage_id)
    if opp:
        await activity_svc.log_activity(
            db, location.id, "opportunity", opp_id, "stage_change",
            description=f"Moved to stage",
            metadata_json={"stage_id": str(stage_id)},
        )

    # Return updated card partial
    opp = await pipeline_svc.get_opportunity(db, opp_id)
    return templates.TemplateResponse("partials/opportunity_card.html", {
        "request": request,
        "opp": opp,
        "location": location,
    })


@router.post("/loc/{slug}/opportunities/{opp_id}/close")
async def opportunity_close(
    request: Request,
    slug: str,
    opp_id: uuid.UUID,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    status = form.get("status", "won")
    opp = await pipeline_svc.close_opportunity(db, opp_id, status)
    if opp:
        await activity_svc.log_activity(
            db, location.id, "opportunity", opp_id, f"closed_{status}",
            description=f"Opportunity closed as {status}"
        )
    return RedirectResponse(f"/loc/{slug}/pipelines/{opp.pipeline_id}" if opp else f"/loc/{slug}/pipelines/", status_code=303)


@router.post("/loc/{slug}/opportunities/{opp_id}/delete")
async def opportunity_delete(
    request: Request,
    slug: str,
    opp_id: uuid.UUID,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    opp = await pipeline_svc.get_opportunity(db, opp_id)
    pipeline_id = opp.pipeline_id if opp else None
    await pipeline_svc.delete_opportunity(db, opp_id)
    redirect = f"/loc/{slug}/pipelines/{pipeline_id}" if pipeline_id else f"/loc/{slug}/pipelines/"
    return RedirectResponse(redirect, status_code=303)
