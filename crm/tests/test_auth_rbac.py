"""Auth + RBAC middleware tests for CRM app."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

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


@pytest.mark.asyncio
async def test_invite_flow_creates_persistent_user(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "auth_secret", "test-secret")
    monkeypatch.setattr(settings, "auth_bootstrap_email", "owner@example.com")
    monkeypatch.setattr(settings, "auth_bootstrap_password", "ownerpass123")
    monkeypatch.setattr(settings, "auth_bootstrap_role", "owner")

    owner_login = await client.post(
        "/auth/login",
        data={"email": "owner@example.com", "password": "ownerpass123", "next": "/locations/"},
        follow_redirects=False,
    )
    assert owner_login.status_code == 303

    invite_resp = await client.post(
        "/auth/invites",
        data={"email": "crmuser@example.com", "role": "manager"},
        cookies=owner_login.cookies,
        follow_redirects=False,
    )
    assert invite_resp.status_code == 303
    qs = parse_qs(urlparse(invite_resp.headers["location"]).query)
    token = qs.get("token", [""])[0]
    assert token

    accept_resp = await client.post(
        "/auth/accept",
        data={"token": token, "password": "crmuserpass123"},
        follow_redirects=False,
    )
    assert accept_resp.status_code == 303

    new_login = await client.post(
        "/auth/login",
        data={"email": "crmuser@example.com", "password": "crmuserpass123", "next": "/locations/"},
        follow_redirects=False,
    )
    assert new_login.status_code == 303
