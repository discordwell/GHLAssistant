"""Pipeline, stage, and opportunity service."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.pipeline import Pipeline, PipelineStage
from ..models.opportunity import Opportunity


# ── Pipeline CRUD ──────────────────────────────────────────────────────────

async def list_pipelines(db: AsyncSession, location_id: uuid.UUID) -> list[Pipeline]:
    stmt = (
        select(Pipeline)
        .where(Pipeline.location_id == location_id)
        .options(selectinload(Pipeline.stages))
        .order_by(Pipeline.name)
    )
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


async def get_pipeline(db: AsyncSession, pipeline_id: uuid.UUID) -> Pipeline | None:
    stmt = (
        select(Pipeline)
        .where(Pipeline.id == pipeline_id)
        .options(selectinload(Pipeline.stages), selectinload(Pipeline.opportunities))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_pipeline(
    db: AsyncSession, location_id: uuid.UUID, name: str, description: str | None = None
) -> Pipeline:
    pipeline = Pipeline(location_id=location_id, name=name, description=description)
    db.add(pipeline)
    await db.commit()
    await db.refresh(pipeline)
    return pipeline


async def delete_pipeline(db: AsyncSession, pipeline_id: uuid.UUID) -> bool:
    stmt = select(Pipeline).where(Pipeline.id == pipeline_id)
    result = await db.execute(stmt)
    pipeline = result.scalar_one_or_none()
    if not pipeline:
        return False
    await db.delete(pipeline)
    await db.commit()
    return True


# ── Stage CRUD ─────────────────────────────────────────────────────────────

async def add_stage(
    db: AsyncSession, pipeline_id: uuid.UUID, name: str, position: int | None = None
) -> PipelineStage:
    if position is None:
        # Auto-assign next position
        stmt = select(func.max(PipelineStage.position)).where(
            PipelineStage.pipeline_id == pipeline_id
        )
        result = await db.execute(stmt)
        max_pos = result.scalar()
        position = (max_pos + 1) if max_pos is not None else 0

    stage = PipelineStage(pipeline_id=pipeline_id, name=name, position=position)
    db.add(stage)
    await db.commit()
    await db.refresh(stage)
    return stage


async def delete_stage(db: AsyncSession, stage_id: uuid.UUID) -> bool:
    stmt = select(PipelineStage).where(PipelineStage.id == stage_id)
    result = await db.execute(stmt)
    stage = result.scalar_one_or_none()
    if not stage:
        return False
    await db.delete(stage)
    await db.commit()
    return True


# ── Opportunity CRUD ───────────────────────────────────────────────────────

async def list_opportunities(
    db: AsyncSession, pipeline_id: uuid.UUID
) -> list[Opportunity]:
    stmt = (
        select(Opportunity)
        .where(Opportunity.pipeline_id == pipeline_id)
        .options(selectinload(Opportunity.contact), selectinload(Opportunity.stage))
        .order_by(Opportunity.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_opportunity(db: AsyncSession, opp_id: uuid.UUID) -> Opportunity | None:
    stmt = (
        select(Opportunity)
        .where(Opportunity.id == opp_id)
        .options(
            selectinload(Opportunity.contact),
            selectinload(Opportunity.stage),
            selectinload(Opportunity.pipeline),
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_opportunity(
    db: AsyncSession, location_id: uuid.UUID, **kwargs
) -> Opportunity:
    opp = Opportunity(location_id=location_id, **kwargs)
    db.add(opp)
    await db.commit()
    await db.refresh(opp)
    return opp


async def update_opportunity(
    db: AsyncSession, opp_id: uuid.UUID, **kwargs
) -> Opportunity | None:
    opp = await get_opportunity(db, opp_id)
    if not opp:
        return None
    for key, value in kwargs.items():
        setattr(opp, key, value)
    await db.commit()
    await db.refresh(opp)
    return opp


async def move_opportunity(
    db: AsyncSession, opp_id: uuid.UUID, stage_id: uuid.UUID
) -> Opportunity | None:
    """Move an opportunity to a different stage."""
    opp = await get_opportunity(db, opp_id)
    if not opp:
        return None
    opp.stage_id = stage_id
    await db.commit()
    await db.refresh(opp)
    return opp


async def close_opportunity(
    db: AsyncSession, opp_id: uuid.UUID, status: str
) -> Opportunity | None:
    """Close an opportunity as won/lost/abandoned."""
    opp = await get_opportunity(db, opp_id)
    if not opp:
        return None
    opp.status = status
    opp.closed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(opp)
    return opp


async def delete_opportunity(db: AsyncSession, opp_id: uuid.UUID) -> bool:
    stmt = select(Opportunity).where(Opportunity.id == opp_id)
    result = await db.execute(stmt)
    opp = result.scalar_one_or_none()
    if not opp:
        return False
    await db.delete(opp)
    await db.commit()
    return True


async def pipeline_stats(
    db: AsyncSession, pipeline_id: uuid.UUID
) -> dict[str, int]:
    """Get opportunity counts per stage for a pipeline."""
    stmt = (
        select(PipelineStage.name, func.count(Opportunity.id))
        .outerjoin(Opportunity, Opportunity.stage_id == PipelineStage.id)
        .where(PipelineStage.pipeline_id == pipeline_id)
        .group_by(PipelineStage.id, PipelineStage.name)
        .order_by(PipelineStage.position)
    )
    result = await db.execute(stmt)
    return {row[0]: row[1] for row in result.all()}
