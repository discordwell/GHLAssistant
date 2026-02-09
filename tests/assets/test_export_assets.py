"""Asset export: media-library remote mapping + upload (stubbed)."""

from __future__ import annotations

import hashlib
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from crm.assets.blobstore import BlobStore
from crm.models.asset import Asset, AssetRef, AssetRemoteMap
from crm.models.base import Base
from crm.models.location import Location
from crm.sync.export_assets import export_assets


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


class _DummyMediaLibrary:
    def __init__(self):
        self.calls: list[dict] = []

    async def upload_path(self, *, path, filename, content_type, location_id):
        self.calls.append(
            {
                "path": str(path),
                "filename": filename,
                "content_type": content_type,
                "location_id": location_id,
            }
        )
        return {"_id": "remote_file_1", "url": "https://example.com/media/remote_file_1.png"}


class _DummyGHL:
    def __init__(self, *, token_id: str | None):
        self.config = type("Cfg", (), {"token_id": token_id})()
        self.media_library = _DummyMediaLibrary()


@pytest.mark.asyncio
async def test_export_assets_maps_existing_media_library_refs_without_token_id(
    db: AsyncSession, location: Location, tmp_path
):
    asset = Asset(
        location_id=location.id,
        sha256="0" * 64,
        size_bytes=1,
        content_type="image/png",
        original_filename="a.png",
        source="media_library",
    )
    db.add(asset)
    await db.flush()

    ref = AssetRef(
        location_id=location.id,
        identity_sha256="1" * 64,
        asset_id=asset.id,
        entity_type="media_library_file",
        entity_id=None,
        remote_entity_id="file_123",
        field_path="url",
        usage="media_library",
        original_url="https://example.com/original.png",
        meta_json={},
    )
    db.add(ref)
    await db.commit()

    ghl = _DummyGHL(token_id=None)
    r = await export_assets(db, location, ghl, blobstore_dir=str(tmp_path))

    # Mapping should still be written even if uploads are skipped.
    assert r.updated == 1
    maps = list((await db.execute(select(AssetRemoteMap))).scalars().all())
    assert len(maps) == 1
    assert maps[0].remote_id == "file_123"
    assert maps[0].remote_url == "https://example.com/original.png"


@pytest.mark.asyncio
async def test_export_assets_uploads_and_persists_remote_map(db: AsyncSession, location: Location, tmp_path):
    data = b"hello"
    sha = hashlib.sha256(data).hexdigest()
    BlobStore(tmp_path).put_bytes_atomic(sha, data)

    asset = Asset(
        location_id=location.id,
        sha256=sha,
        size_bytes=len(data),
        content_type="text/plain",
        original_filename=None,
        source="funnel_page_html",
    )
    db.add(asset)
    await db.commit()

    ghl = _DummyGHL(token_id="tok")
    r1 = await export_assets(
        db,
        location,
        ghl,
        blobstore_dir=str(tmp_path),
        limit=10,
        sources_csv="funnel_page_html",
    )
    assert r1.created == 1
    maps = list((await db.execute(select(AssetRemoteMap))).scalars().all())
    assert len(maps) == 1
    assert maps[0].asset_id == asset.id
    assert maps[0].remote_id == "remote_file_1"
    assert maps[0].remote_url == "https://example.com/media/remote_file_1.png"

    # Idempotent: second run should skip uploading.
    r2 = await export_assets(
        db,
        location,
        ghl,
        blobstore_dir=str(tmp_path),
        limit=10,
        sources_csv="funnel_page_html",
    )
    assert r2.created == 0
    assert r2.skipped >= 1

