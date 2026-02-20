"""Auth + RBAC middleware tests for workflows app."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

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
        data={"email": "owner@example.com", "password": "ownerpass123", "next": "/"},
        follow_redirects=False,
    )
    assert owner_login.status_code == 303

    invite_resp = await client.post(
        "/auth/invites",
        data={"email": "newuser@example.com", "role": "manager"},
        cookies=owner_login.cookies,
        follow_redirects=False,
    )
    assert invite_resp.status_code == 303
    qs = parse_qs(urlparse(invite_resp.headers["location"]).query)
    token = qs.get("token", [""])[0]
    assert token

    accept_resp = await client.post(
        "/auth/accept",
        data={"token": token, "password": "newuserpass123"},
        follow_redirects=False,
    )
    assert accept_resp.status_code == 303

    new_login = await client.post(
        "/auth/login",
        data={"email": "newuser@example.com", "password": "newuserpass123", "next": "/"},
        follow_redirects=False,
    )
    assert new_login.status_code == 303


@pytest.mark.asyncio
async def test_user_management_can_disable_account_and_preserve_owner(
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
        data={"email": "owner@example.com", "password": "ownerpass123", "next": "/"},
        follow_redirects=False,
    )
    assert owner_login.status_code == 303

    invite_resp = await client.post(
        "/auth/invites",
        data={"email": "ops@example.com", "role": "manager"},
        cookies=owner_login.cookies,
        follow_redirects=False,
    )
    token = parse_qs(urlparse(invite_resp.headers["location"]).query).get("token", [""])[0]
    assert token

    accept_resp = await client.post(
        "/auth/accept",
        data={"token": token, "password": "opspass123"},
        follow_redirects=False,
    )
    assert accept_resp.status_code == 303

    disable_resp = await client.post(
        "/auth/users",
        data={"email": "ops@example.com", "role": "manager", "is_active": "false"},
        cookies=owner_login.cookies,
        follow_redirects=False,
    )
    assert disable_resp.status_code == 303
    assert disable_resp.headers["location"].startswith("/auth/users?msg=User+updated")

    disabled_login = await client.post(
        "/auth/login",
        data={"email": "ops@example.com", "password": "opspass123", "next": "/"},
        follow_redirects=False,
    )
    assert disabled_login.status_code == 200

    reject_disable_owner = await client.post(
        "/auth/users",
        data={"email": "owner@example.com", "role": "owner", "is_active": "false"},
        cookies=owner_login.cookies,
        follow_redirects=False,
    )
    assert reject_disable_owner.status_code == 303
    assert reject_disable_owner.headers["location"].startswith("/auth/users?msg=Update+rejected")
