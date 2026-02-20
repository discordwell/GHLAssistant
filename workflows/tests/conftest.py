"""Async test fixtures for Workflow Builder tests using SQLite."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from workflows.config import settings
from workflows.models import Base
from workflows.database import get_db


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db(engine):
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(engine):
    """HTTPX async test client against the Workflow Builder app."""
    from workflows.app import app

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    class CSRFAwareAsyncClient(AsyncClient):
        async def post(self, url, *args, **kwargs):
            url_str = str(url)
            if url_str in {"/auth/login", "/auth/accept"}:
                data = kwargs.get("data")
                if isinstance(data, dict) and "csrf_token" not in data:
                    token = "test-csrf-token"
                    kwargs["data"] = {**data, "csrf_token": token}
                    cookies = kwargs.get("cookies")
                    cookies_dict = dict(cookies or {})
                    cookies_dict.setdefault(f"{settings.auth_cookie_name}_csrf", token)
                    kwargs["cookies"] = cookies_dict
            return await super().post(url, *args, **kwargs)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with CSRFAwareAsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
