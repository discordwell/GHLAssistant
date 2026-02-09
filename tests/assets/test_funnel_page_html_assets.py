"""Asset discovery: funnel page HTML scanning (URLs + data URIs)."""

from __future__ import annotations

import base64
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from crm.assets.blobstore import BlobStore
from crm.assets.html import sha256_hex
from crm.models.asset import Asset, AssetJob, AssetRef
from crm.models.base import Base
from crm.models.funnel import Funnel, FunnelPage
from crm.models.location import Location
from crm.sync.import_assets import discover_funnel_page_html_assets


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
async def test_discover_funnel_page_html_assets_creates_refs_jobs_and_data_uri_assets(
    db: AsyncSession,
    location: Location,
    tmp_path,
):
    funnel = Funnel(
        location_id=location.id,
        name="Main Funnel",
        description=None,
        is_published=True,
        ghl_id="ghl_funnel_1",
        ghl_location_id=location.ghl_location_id,
    )
    db.add(funnel)
    await db.flush()

    data_bytes = b"hello-asset"
    data_b64 = base64.b64encode(data_bytes).decode("ascii")

    html = (
        '<img src="https://example.com/a.png">\n'
        '<a href="https://example.com/file.pdf">Download</a>\n'
        "<div style=\"background-image:url('https://example.com/bg.jpg?x=1&amp;y=2')\"></div>\n"
        '<img srcset="https://example.com/one.jpg 1x, https://example.com/two.jpg 2x">\n'
        f'<img src="data:image/png;base64,{data_b64}">\n'
    )

    page = FunnelPage(
        funnel_id=funnel.id,
        name="Landing",
        url_slug="landing",
        content_html=html,
        position=0,
        is_published=True,
        ghl_id="ghl_page_1",
    )
    db.add(page)
    await db.commit()

    blobstore = BlobStore(tmp_path / "blobstore")
    ar = await discover_funnel_page_html_assets(db, location, blobstore=blobstore)

    assert ar.refs_created == 6
    assert ar.jobs_created == 5
    assert ar.assets_created == 1
    assert ar.errors == []

    refs = list((await db.execute(select(AssetRef))).scalars().all())
    jobs = list((await db.execute(select(AssetJob))).scalars().all())
    assets = list((await db.execute(select(Asset))).scalars().all())

    assert len(refs) == 6
    assert len(jobs) == 5
    assert len(assets) == 1

    # Ensure the style-attr URL got HTML-unescaped for fetch jobs.
    assert any(j.url == "https://example.com/bg.jpg?x=1&y=2" for j in jobs)

    # Ensure data URI bytes were persisted to blobstore.
    asset = assets[0]
    assert asset.sha256 == sha256_hex(data_bytes)
    blob_path = blobstore.path_for_sha256(asset.sha256)
    assert blob_path.is_file()
    assert blob_path.read_bytes() == data_bytes

    # Idempotent: running again should not create new rows.
    ar2 = await discover_funnel_page_html_assets(db, location, blobstore=blobstore)
    assert ar2.refs_created == 0
    assert ar2.jobs_created == 0
    assert ar2.assets_created == 0

    refs2 = list((await db.execute(select(AssetRef))).scalars().all())
    jobs2 = list((await db.execute(select(AssetJob))).scalars().all())
    assets2 = list((await db.execute(select(Asset))).scalars().all())
    assert len(refs2) == 6
    assert len(jobs2) == 5
    assert len(assets2) == 1

