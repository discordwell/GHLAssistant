"""Regression tests for workflow raw preservation import."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from crm.models.base import Base
from crm.models.ghl_raw import GHLRawEntity
from crm.models.location import Location
from crm.sync.import_workflows import import_workflows


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def location(db: AsyncSession) -> Location:
    loc = Location(
        id=uuid.uuid4(),
        name="Test Location",
        slug="test-location",
        timezone="UTC",
        ghl_location_id="ghl_loc_123",
    )
    db.add(loc)
    await db.commit()
    await db.refresh(loc)
    return loc


@pytest.mark.asyncio
async def test_import_workflows_creates_and_updates_raw(db: AsyncSession, location: Location):
    workflows = [
        {"id": "wf_1", "name": "Welcome", "status": "published"},
        {"id": "wf_2", "name": "Nurture", "status": "draft"},
    ]
    details_by_id = {
        "wf_1": {"workflow": {"id": "wf_1", "name": "Welcome", "steps": [{"type": "sms"}]}},
        "wf_2": {"workflow": {"id": "wf_2", "name": "Nurture", "steps": []}},
    }

    result = await import_workflows(db, location, workflows, details_by_id=details_by_id)
    assert result.created == 2

    rows = list(
        (
            await db.execute(
                select(GHLRawEntity).where(
                    GHLRawEntity.location_id == location.id,
                    GHLRawEntity.entity_type == "workflow",
                )
            )
        ).scalars()
    )
    assert len(rows) == 2

    # Second run should update (not create)
    result2 = await import_workflows(db, location, workflows, details_by_id=details_by_id)
    assert result2.updated == 2

