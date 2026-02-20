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
        data={"email": "owner@example.com", "password": "ownerpass123", "next": "/locations/"},
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
        data={"email": "ops@example.com", "password": "opspass123", "next": "/locations/"},
        follow_redirects=False,
    )
    assert disabled_login.status_code == 200
    assert "Invalid credentials" in disabled_login.text

    reject_disable_owner = await client.post(
        "/auth/users",
        data={"email": "owner@example.com", "role": "owner", "is_active": "false"},
        cookies=owner_login.cookies,
        follow_redirects=False,
    )
    assert reject_disable_owner.status_code == 303
    assert reject_disable_owner.headers["location"].startswith("/auth/users?msg=Update+rejected")


@pytest.mark.asyncio
async def test_bootstrap_fallback_does_not_bypass_disabled_db_account(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "auth_secret", "test-secret")
    monkeypatch.setattr(settings, "auth_bootstrap_email", "owner@example.com")
    monkeypatch.setattr(settings, "auth_bootstrap_password", "ownerpass123")
    monkeypatch.setattr(settings, "auth_bootstrap_role", "owner")

    owner1_login = await client.post(
        "/auth/login",
        data={"email": "owner@example.com", "password": "ownerpass123", "next": "/locations/"},
        follow_redirects=False,
    )
    assert owner1_login.status_code == 303

    invite_resp = await client.post(
        "/auth/invites",
        data={"email": "owner2@example.com", "role": "owner"},
        cookies=owner1_login.cookies,
        follow_redirects=False,
    )
    token = parse_qs(urlparse(invite_resp.headers["location"]).query).get("token", [""])[0]
    assert token

    accept_resp = await client.post(
        "/auth/accept",
        data={"token": token, "password": "owner2pass123"},
        follow_redirects=False,
    )
    assert accept_resp.status_code == 303

    owner2_login = await client.post(
        "/auth/login",
        data={"email": "owner2@example.com", "password": "owner2pass123", "next": "/locations/"},
        follow_redirects=False,
    )
    assert owner2_login.status_code == 303

    disable_owner1 = await client.post(
        "/auth/users",
        data={"email": "owner@example.com", "role": "owner", "is_active": "false"},
        cookies=owner2_login.cookies,
        follow_redirects=False,
    )
    assert disable_owner1.status_code == 303
    assert disable_owner1.headers["location"].startswith("/auth/users?msg=User+updated")

    owner1_disabled_login = await client.post(
        "/auth/login",
        data={"email": "owner@example.com", "password": "ownerpass123", "next": "/locations/"},
        follow_redirects=False,
    )
    assert owner1_disabled_login.status_code == 200
    assert "Invalid credentials" in owner1_disabled_login.text


@pytest.mark.asyncio
async def test_manager_cannot_modify_owner_or_self_escalate(
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
        data={"email": "manager@example.com", "role": "manager"},
        cookies=owner_login.cookies,
        follow_redirects=False,
    )
    token = parse_qs(urlparse(invite_resp.headers["location"]).query).get("token", [""])[0]
    assert token

    accept_resp = await client.post(
        "/auth/accept",
        data={"token": token, "password": "managerpass123"},
        follow_redirects=False,
    )
    assert accept_resp.status_code == 303

    manager_login = await client.post(
        "/auth/login",
        data={"email": "manager@example.com", "password": "managerpass123", "next": "/locations/"},
        follow_redirects=False,
    )
    assert manager_login.status_code == 303

    reject_owner_change = await client.post(
        "/auth/users",
        data={"email": "owner@example.com", "role": "manager", "is_active": "true"},
        cookies=manager_login.cookies,
        follow_redirects=False,
    )
    assert reject_owner_change.status_code == 303
    assert reject_owner_change.headers["location"].startswith("/auth/users?msg=Update+rejected")

    reject_self_escalate = await client.post(
        "/auth/users",
        data={"email": "manager@example.com", "role": "owner", "is_active": "true"},
        cookies=manager_login.cookies,
        follow_redirects=False,
    )
    assert reject_self_escalate.status_code == 303
    assert reject_self_escalate.headers["location"].startswith("/auth/users?msg=Update+rejected")

    owner_relogin = await client.post(
        "/auth/login",
        data={"email": "owner@example.com", "password": "ownerpass123", "next": "/locations/"},
        follow_redirects=False,
    )
    assert owner_relogin.status_code == 303


@pytest.mark.asyncio
async def test_password_change_rotates_credentials(
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

    changed = await client.post(
        "/auth/password",
        data={
            "current_password": "ownerpass123",
            "new_password": "ownerpass456",
            "confirm_password": "ownerpass456",
        },
        cookies=owner_login.cookies,
        follow_redirects=False,
    )
    assert changed.status_code == 303
    assert changed.headers["location"].startswith("/auth/password?msg=Password+updated")

    old_login = await client.post(
        "/auth/login",
        data={"email": "owner@example.com", "password": "ownerpass123", "next": "/locations/"},
        follow_redirects=False,
    )
    assert old_login.status_code == 200
    assert "Invalid credentials" in old_login.text

    new_login = await client.post(
        "/auth/login",
        data={"email": "owner@example.com", "password": "ownerpass456", "next": "/locations/"},
        follow_redirects=False,
    )
    assert new_login.status_code == 303


@pytest.mark.asyncio
async def test_password_change_rejects_wrong_current_password(
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

    rejected = await client.post(
        "/auth/password",
        data={
            "current_password": "wrongpass",
            "new_password": "ownerpass456",
            "confirm_password": "ownerpass456",
        },
        cookies=owner_login.cookies,
        follow_redirects=False,
    )
    assert rejected.status_code == 303
    assert rejected.headers["location"].startswith("/auth/password?msg=Current+password+invalid")


@pytest.mark.asyncio
async def test_disabled_user_active_session_is_revoked_immediately(
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
        data={"email": "agent@example.com", "role": "manager"},
        cookies=owner_login.cookies,
        follow_redirects=False,
    )
    token = parse_qs(urlparse(invite_resp.headers["location"]).query).get("token", [""])[0]
    assert token

    accept_resp = await client.post(
        "/auth/accept",
        data={"token": token, "password": "agentpass123"},
        follow_redirects=False,
    )
    assert accept_resp.status_code == 303

    agent_login = await client.post(
        "/auth/login",
        data={"email": "agent@example.com", "password": "agentpass123", "next": "/locations/"},
        follow_redirects=False,
    )
    assert agent_login.status_code == 303

    disable_agent = await client.post(
        "/auth/users",
        data={"email": "agent@example.com", "role": "manager", "is_active": "false"},
        cookies=owner_login.cookies,
        follow_redirects=False,
    )
    assert disable_agent.status_code == 303
    assert disable_agent.headers["location"].startswith("/auth/users?msg=User+updated")

    revoked_access = await client.get("/", cookies=agent_login.cookies, follow_redirects=False)
    assert revoked_access.status_code == 303
    assert revoked_access.headers["location"].startswith("/auth/login")


@pytest.mark.asyncio
async def test_demotion_applies_to_auth_routes_without_relogin(
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
        data={"email": "manager2@example.com", "role": "manager"},
        cookies=owner_login.cookies,
        follow_redirects=False,
    )
    token = parse_qs(urlparse(invite_resp.headers["location"]).query).get("token", [""])[0]
    assert token

    accept_resp = await client.post(
        "/auth/accept",
        data={"token": token, "password": "manager2pass123"},
        follow_redirects=False,
    )
    assert accept_resp.status_code == 303

    manager_login = await client.post(
        "/auth/login",
        data={"email": "manager2@example.com", "password": "manager2pass123", "next": "/locations/"},
        follow_redirects=False,
    )
    assert manager_login.status_code == 303

    demote_manager = await client.post(
        "/auth/users",
        data={"email": "manager2@example.com", "role": "viewer", "is_active": "true"},
        cookies=owner_login.cookies,
        follow_redirects=False,
    )
    assert demote_manager.status_code == 303
    assert demote_manager.headers["location"].startswith("/auth/users?msg=User+updated")

    manager_invite_attempt = await client.post(
        "/auth/invites",
        data={"email": "shouldfail@example.com", "role": "viewer"},
        cookies=manager_login.cookies,
        follow_redirects=False,
    )
    assert manager_invite_attempt.status_code == 303
    assert manager_invite_attempt.headers["location"].startswith("/auth/login")
