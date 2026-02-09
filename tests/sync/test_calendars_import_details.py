"""Regression tests for calendars importer detail preservation."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from crm.models.base import Base
from crm.models.calendar import Calendar
from crm.models.ghl_raw import GHLRawEntity
from crm.models.location import Location
from crm.sync.import_calendars import import_calendars


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
async def test_import_calendars_uses_detail_payload(db: AsyncSession, location: Location):
    calendars_data = [{"id": "cal_1", "name": "Main Calendar", "slotDuration": 30}]
    details_by_calendar = {
        "cal_1": {
            "calendar": {
                "description": "Detail description",
                "timezone": "America/Los_Angeles",
                "slotDuration": 15,
                "bufferBefore": 5,
                "bufferAfter": 10,
                "isActive": False,
            }
        }
    }

    result = await import_calendars(
        db,
        location,
        calendars_data,
        appointments_data={},
        details_by_calendar=details_by_calendar,
    )
    assert result.created == 1

    cal = (await db.execute(select(Calendar))).scalar_one()
    assert cal.name == "Main Calendar"
    assert cal.description == "Detail description"
    assert cal.timezone == "America/Los_Angeles"
    assert cal.slot_duration == 15
    assert cal.buffer_before == 5
    assert cal.buffer_after == 10
    assert cal.is_active is False

    raw = (
        await db.scalar(
            select(GHLRawEntity).where(
                GHLRawEntity.location_id == location.id,
                GHLRawEntity.entity_type == "calendar",
                GHLRawEntity.ghl_id == "cal_1",
            )
        )
    )
    assert raw is not None
    assert isinstance(raw.payload_json, dict)
    assert "list" in raw.payload_json and "detail" in raw.payload_json

