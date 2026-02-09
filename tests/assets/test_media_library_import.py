"""Media library import: enqueue download jobs + preserve refs."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from crm.models.base import Base
from crm.models.asset import AssetJob, AssetRef
from crm.models.ghl_raw import GHLRawEntity
from crm.models.location import Location
from crm.sync.import_media_library import import_media_library


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
async def test_import_media_library_creates_refs_jobs_and_raw_entities(db: AsyncSession, location: Location):
    items = [
        {
            "id": "file_1",
            "url": "https://example.com/a.png",
            "name": "a.png",
            "contentType": "image/png",
        },
        {
            "_id": "file_2",
            "fileUrl": "https://example.com/b.pdf",
            "filename": "b.pdf",
        },
    ]

    r1 = await import_media_library(db, location=location, items=items, source="api")
    assert r1.created == 2
    assert r1.errors == []

    refs = list(
        (await db.execute(select(AssetRef).where(AssetRef.location_id == location.id)))
        .scalars()
        .all()
    )
    assert len(refs) == 2
    assert sorted(ref.remote_entity_id for ref in refs) == ["file_1", "file_2"]
    assert all(ref.entity_type == "media_library_file" for ref in refs)
    assert all(ref.usage == "media_library" for ref in refs)
    assert all(ref.field_path == "url" for ref in refs)

    jobs = list(
        (
            await db.execute(
                select(AssetJob).where(
                    AssetJob.location_id == location.id,
                    AssetJob.job_type == "download",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(jobs) == 2
    assert sorted(j.url for j in jobs) == ["https://example.com/a.png", "https://example.com/b.pdf"]

    raws = list(
        (
            await db.execute(
                select(GHLRawEntity).where(
                    GHLRawEntity.location_id == location.id,
                    GHLRawEntity.entity_type == "media_library_file",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(raws) == 2
    assert sorted(r.ghl_id for r in raws) == ["file_1", "file_2"]

    # Idempotent: second run should not create duplicates.
    r2 = await import_media_library(db, location=location, items=items, source="api")
    assert r2.created == 0

    refs2 = list(
        (await db.execute(select(AssetRef).where(AssetRef.location_id == location.id)))
        .scalars()
        .all()
    )
    jobs2 = list(
        (
            await db.execute(
                select(AssetJob).where(
                    AssetJob.location_id == location.id,
                    AssetJob.job_type == "download",
                )
            )
        )
        .scalars()
        .all()
    )
    raws2 = list(
        (
            await db.execute(
                select(GHLRawEntity).where(
                    GHLRawEntity.location_id == location.id,
                    GHLRawEntity.entity_type == "media_library_file",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(refs2) == 2
    assert len(jobs2) == 2
    assert len(raws2) == 2

