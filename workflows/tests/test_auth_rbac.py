"""Auth + RBAC middleware tests for workflows app."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from workflows.config import settings


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


@pytest.mark.asyncio
async def test_viewer_role_cannot_write(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "auth_secret", "test-secret")
    monkeypatch.setattr(settings, "auth_bootstrap_email", "viewer@example.com")
    monkeypatch.setattr(settings, "auth_bootstrap_password", "pass123")
    monkeypatch.setattr(settings, "auth_bootstrap_role", "viewer")

    login = await client.post(
        "/auth/login",
        data={"email": "viewer@example.com", "password": "pass123", "next": "/"},
        follow_redirects=False,
    )
    assert login.status_code == 303

    resp = await client.post(
        "/workflows/new",
        data={"name": "Blocked", "description": "", "trigger_type": "manual"},
        cookies=login.cookies,
    )
    assert resp.status_code == 403

