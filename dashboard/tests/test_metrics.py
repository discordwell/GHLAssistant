"""Tests for the metrics service."""

from __future__ import annotations

import pytest

from dashboard.services.metrics_svc import get_metrics


@pytest.mark.asyncio
async def test_metrics_empty_databases(multi_db):
    """Empty databases should return all zeros."""
    metrics = await get_metrics(db=multi_db)
    assert metrics["crm_contacts"] == 0
    assert metrics["crm_opportunities"] == 0
    assert metrics["crm_pipelines"] == 0
    assert metrics["hiring_candidates"] == 0
    assert metrics["hiring_positions"] == 0
    assert metrics["hiring_hired"] == 0
    assert metrics["wf_workflows"] == 0
    assert metrics["wf_executions"] == 0
    assert metrics["wf_failed"] == 0


@pytest.mark.asyncio
async def test_metrics_seeded_crm(seeded_db):
    """CRM metrics match seeded data."""
    metrics = await get_metrics(db=seeded_db)
    assert metrics["crm_contacts"] == 5
    assert metrics["crm_opportunities"] == 3
    assert metrics["crm_pipelines"] == 2


@pytest.mark.asyncio
async def test_metrics_seeded_hiring(seeded_db):
    """Hiring metrics match seeded data."""
    metrics = await get_metrics(db=seeded_db)
    assert metrics["hiring_candidates"] == 4
    assert metrics["hiring_positions"] == 3
    assert metrics["hiring_hired"] == 1


@pytest.mark.asyncio
async def test_metrics_seeded_workflows(seeded_db):
    """Workflow metrics match seeded data."""
    metrics = await get_metrics(db=seeded_db)
    assert metrics["wf_workflows"] == 2
    assert metrics["wf_executions"] == 3
    assert metrics["wf_failed"] == 1


@pytest.mark.asyncio
async def test_metrics_returns_all_keys(seeded_db):
    """All 9 metric keys are present."""
    metrics = await get_metrics(db=seeded_db)
    expected_keys = {
        "crm_contacts", "crm_opportunities", "crm_pipelines",
        "hiring_candidates", "hiring_positions", "hiring_hired",
        "wf_workflows", "wf_executions", "wf_failed",
    }
    assert set(metrics.keys()) == expected_keys


@pytest.mark.asyncio
async def test_metrics_values_are_integers(seeded_db):
    """All metric values should be integers."""
    metrics = await get_metrics(db=seeded_db)
    for key, value in metrics.items():
        assert isinstance(value, int), f"{key} should be int, got {type(value)}"


@pytest.mark.asyncio
async def test_metrics_missing_crm_db_graceful():
    """When CRM database is unreachable, returns 0s for CRM metrics."""
    from dashboard.database import MultiDB
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import create_engine

    # Create a DB pointing at nonexistent file
    bad_db = MultiDB.__new__(MultiDB)
    bad_db.crm_engine = create_async_engine("sqlite+aiosqlite:///nonexistent_crm.db", echo=False)
    bad_db.wf_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    bad_db.hiring_engine = create_engine("sqlite:///:memory:", echo=False)

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    bad_db._crm_session = async_sessionmaker(bad_db.crm_engine, class_=AsyncSession, expire_on_commit=False)
    bad_db._wf_session = async_sessionmaker(bad_db.wf_engine, class_=AsyncSession, expire_on_commit=False)

    metrics = await get_metrics(db=bad_db)
    assert metrics["crm_contacts"] == 0
    assert metrics["crm_opportunities"] == 0
    assert metrics["crm_pipelines"] == 0

    await bad_db.crm_engine.dispose()
    await bad_db.wf_engine.dispose()
    bad_db.hiring_engine.dispose()


@pytest.mark.asyncio
async def test_metrics_missing_hiring_db_graceful():
    """When Hiring database is unreachable, returns 0s for Hiring metrics."""
    from dashboard.database import MultiDB
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy import create_engine

    bad_db = MultiDB.__new__(MultiDB)
    bad_db.crm_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    bad_db.wf_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    bad_db.hiring_engine = create_engine("sqlite:///nonexistent_hiring.db", echo=False)
    bad_db._crm_session = async_sessionmaker(bad_db.crm_engine, class_=AsyncSession, expire_on_commit=False)
    bad_db._wf_session = async_sessionmaker(bad_db.wf_engine, class_=AsyncSession, expire_on_commit=False)

    metrics = await get_metrics(db=bad_db)
    assert metrics["hiring_candidates"] == 0
    assert metrics["hiring_positions"] == 0
    assert metrics["hiring_hired"] == 0

    await bad_db.crm_engine.dispose()
    await bad_db.wf_engine.dispose()
    bad_db.hiring_engine.dispose()


@pytest.mark.asyncio
async def test_metrics_combined_total(seeded_db):
    """Verify combined sum across all apps."""
    metrics = await get_metrics(db=seeded_db)
    total = sum(metrics.values())
    # 5+3+2 + 4+3+1 + 2+3+1 = 24
    assert total == 24
