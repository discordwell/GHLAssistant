"""Tests for the activity service."""

from __future__ import annotations

import pytest

from dashboard.services.activity_svc import get_recent_activity, ActivityItem


@pytest.mark.asyncio
async def test_activity_empty_databases(multi_db):
    """Empty databases should return empty list."""
    items = await get_recent_activity(db=multi_db)
    assert items == []


@pytest.mark.asyncio
async def test_activity_seeded_returns_items(seeded_db):
    """Seeded databases should return activity items."""
    items = await get_recent_activity(db=seeded_db)
    assert len(items) > 0


@pytest.mark.asyncio
async def test_activity_sorted_by_timestamp_desc(seeded_db):
    """Items should be sorted newest-first."""
    items = await get_recent_activity(db=seeded_db)
    for i in range(len(items) - 1):
        assert items[i].timestamp >= items[i + 1].timestamp


@pytest.mark.asyncio
async def test_activity_sources_present(seeded_db):
    """All 3 sources should be represented in the activity feed."""
    items = await get_recent_activity(db=seeded_db)
    sources = {item.source for item in items}
    assert "crm" in sources
    assert "hiring" in sources
    assert "workflows" in sources


@pytest.mark.asyncio
async def test_activity_crm_items(seeded_db):
    """CRM activity items have correct source and action."""
    items = await get_recent_activity(db=seeded_db)
    crm_items = [i for i in items if i.source == "crm"]
    assert len(crm_items) == 3
    assert all(i.action == "created" for i in crm_items)


@pytest.mark.asyncio
async def test_activity_hiring_items(seeded_db):
    """Hiring activity items have correct source and action."""
    items = await get_recent_activity(db=seeded_db)
    hiring_items = [i for i in items if i.source == "hiring"]
    assert len(hiring_items) == 2
    assert all(i.action == "stage_change" for i in hiring_items)


@pytest.mark.asyncio
async def test_activity_workflow_items(seeded_db):
    """Workflow log items have correct source and event."""
    items = await get_recent_activity(db=seeded_db)
    wf_items = [i for i in items if i.source == "workflows"]
    assert len(wf_items) == 2
    assert all(i.action == "step_completed" for i in wf_items)


@pytest.mark.asyncio
async def test_activity_limit_parameter(seeded_db):
    """Limit parameter should cap the number of results."""
    items = await get_recent_activity(db=seeded_db, limit=3)
    assert len(items) <= 3


@pytest.mark.asyncio
async def test_activity_item_has_all_fields(seeded_db):
    """Each ActivityItem should have source, action, description, timestamp."""
    items = await get_recent_activity(db=seeded_db)
    for item in items:
        assert isinstance(item, ActivityItem)
        assert item.source in ("crm", "hiring", "workflows")
        assert isinstance(item.action, str)
        assert isinstance(item.description, str)
        assert item.timestamp is not None


@pytest.mark.asyncio
async def test_activity_missing_db_graceful():
    """When a database is unavailable, activity from other DBs still works."""
    from dashboard.database import MultiDB
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy import create_engine

    bad_db = MultiDB.__new__(MultiDB)
    bad_db.crm_engine = create_async_engine("sqlite+aiosqlite:///nonexistent.db", echo=False)
    bad_db.wf_engine = create_async_engine("sqlite+aiosqlite:///nonexistent.db", echo=False)
    bad_db.hiring_engine = create_engine("sqlite:///nonexistent.db", echo=False)
    bad_db._crm_session = async_sessionmaker(bad_db.crm_engine, class_=AsyncSession, expire_on_commit=False)
    bad_db._wf_session = async_sessionmaker(bad_db.wf_engine, class_=AsyncSession, expire_on_commit=False)

    items = await get_recent_activity(db=bad_db)
    assert items == []

    await bad_db.crm_engine.dispose()
    await bad_db.wf_engine.dispose()
    bad_db.hiring_engine.dispose()
