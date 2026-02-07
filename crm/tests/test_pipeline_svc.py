"""Test pipeline service."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from crm.models.location import Location
from crm.services import pipeline_svc, contact_svc


@pytest.mark.asyncio
async def test_create_pipeline(db: AsyncSession, location: Location):
    pipeline = await pipeline_svc.create_pipeline(db, location.id, "Sales", "Main pipeline")
    assert pipeline.name == "Sales"
    assert pipeline.description == "Main pipeline"


@pytest.mark.asyncio
async def test_add_stages(db: AsyncSession, location: Location):
    pipeline = await pipeline_svc.create_pipeline(db, location.id, "Deals")
    s1 = await pipeline_svc.add_stage(db, pipeline.id, "Lead")
    s2 = await pipeline_svc.add_stage(db, pipeline.id, "Qualified")
    assert s1.position == 0
    assert s2.position == 1


@pytest.mark.asyncio
async def test_list_pipelines(db: AsyncSession, location: Location):
    await pipeline_svc.create_pipeline(db, location.id, "Pipeline A")
    await pipeline_svc.create_pipeline(db, location.id, "Pipeline B")

    pipelines = await pipeline_svc.list_pipelines(db, location.id)
    assert len(pipelines) == 2


@pytest.mark.asyncio
async def test_create_opportunity(db: AsyncSession, location: Location):
    pipeline = await pipeline_svc.create_pipeline(db, location.id, "Opps")
    stage = await pipeline_svc.add_stage(db, pipeline.id, "New")

    opp = await pipeline_svc.create_opportunity(
        db, location.id,
        name="Big Deal", pipeline_id=pipeline.id, stage_id=stage.id,
        monetary_value=5000.0,
    )
    assert opp.name == "Big Deal"
    assert opp.monetary_value == 5000.0
    assert opp.status == "open"


@pytest.mark.asyncio
async def test_move_opportunity(db: AsyncSession, location: Location):
    pipeline = await pipeline_svc.create_pipeline(db, location.id, "Move Test")
    s1 = await pipeline_svc.add_stage(db, pipeline.id, "Stage 1")
    s2 = await pipeline_svc.add_stage(db, pipeline.id, "Stage 2")

    opp = await pipeline_svc.create_opportunity(
        db, location.id,
        name="Movable", pipeline_id=pipeline.id, stage_id=s1.id,
    )
    assert opp.stage_id == s1.id

    moved = await pipeline_svc.move_opportunity(db, opp.id, s2.id)
    assert moved.stage_id == s2.id


@pytest.mark.asyncio
async def test_close_opportunity(db: AsyncSession, location: Location):
    pipeline = await pipeline_svc.create_pipeline(db, location.id, "Close Test")
    stage = await pipeline_svc.add_stage(db, pipeline.id, "New")

    opp = await pipeline_svc.create_opportunity(
        db, location.id,
        name="Closeable", pipeline_id=pipeline.id, stage_id=stage.id,
    )
    closed = await pipeline_svc.close_opportunity(db, opp.id, "won")
    assert closed.status == "won"
    assert closed.closed_at is not None


@pytest.mark.asyncio
async def test_pipeline_stats(db: AsyncSession, location: Location):
    pipeline = await pipeline_svc.create_pipeline(db, location.id, "Stats Test")
    s1 = await pipeline_svc.add_stage(db, pipeline.id, "Lead")
    s2 = await pipeline_svc.add_stage(db, pipeline.id, "Won")

    await pipeline_svc.create_opportunity(db, location.id, name="O1", pipeline_id=pipeline.id, stage_id=s1.id)
    await pipeline_svc.create_opportunity(db, location.id, name="O2", pipeline_id=pipeline.id, stage_id=s1.id)
    await pipeline_svc.create_opportunity(db, location.id, name="O3", pipeline_id=pipeline.id, stage_id=s2.id)

    stats = await pipeline_svc.pipeline_stats(db, pipeline.id)
    assert stats["Lead"] == 2
    assert stats["Won"] == 1


@pytest.mark.asyncio
async def test_delete_pipeline(db: AsyncSession, location: Location):
    pipeline = await pipeline_svc.create_pipeline(db, location.id, "Deletable")
    result = await pipeline_svc.delete_pipeline(db, pipeline.id)
    assert result is True

    fetched = await pipeline_svc.get_pipeline(db, pipeline.id)
    assert fetched is None
