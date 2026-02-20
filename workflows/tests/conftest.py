"""Async test fixtures for Workflow Builder tests using SQLite."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from workflows.config import settings
from workflows.models.auth import AuthAccount
from workflows.models import Base
from workflows.database import get_db
from maxlevel.platform_auth import hash_password


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
            if url_str == "/auth/login":
                data = kwargs.get("data")
                if isinstance(data, dict):
                    email = str(data.get("email", "")).strip().lower()
                    password = str(data.get("password", ""))
                    bootstrap_email = str(getattr(settings, "auth_bootstrap_email", "")).strip().lower()
                    bootstrap_password = str(getattr(settings, "auth_bootstrap_password", ""))
                    if (
                        bootstrap_email
                        and bootstrap_password
                        and email == bootstrap_email
                        and password == bootstrap_password
                    ):
                        async with session_factory() as session:
                            account = (
                                await session.execute(
                                    select(AuthAccount).where(AuthAccount.email == bootstrap_email)
                                )
                            ).scalar_one_or_none()
                            if not account:
                                session.add(
                                    AuthAccount(
                                        email=bootstrap_email,
                                        password_hash=hash_password(bootstrap_password),
                                        role=str(getattr(settings, "auth_bootstrap_role", "owner")),
                                        is_active=True,
                                    )
                                )
                                await session.commit()
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
