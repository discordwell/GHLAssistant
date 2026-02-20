"""Auth + RBAC middleware tests for CRM app."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from crm.config import settings


@pytest.mark.asyncio
async def test_requires_login_when_auth_enabled(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "auth_secret", "test-secret")
    monkeypatch.setattr(settings, "auth_bootstrap_email", "owner@example.com")
    monkeypatch.setattr(settings, "auth_bootstrap_password", "pass123")
    monkeypatch.setattr(settings, "auth_bootstrap_role", "owner")

    resp = await client.get("/")
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/auth/login")

