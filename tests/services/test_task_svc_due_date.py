"""Task service robustness tests.

These are specifically aimed at Postgres correctness: Date columns require
Python `date` objects; passing strings can "work" in SQLite but will fail in
asyncpg bindings.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from crm.models.base import Base
from crm.services import task_svc


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_create_task_coerces_due_date_string_to_date(db: AsyncSession):
    task = await task_svc.create_task(
        db,
        uuid.uuid4(),
        title="Test",
        due_date="2026-02-10",
    )
    assert task.due_date == date(2026, 2, 10)

