"""Auth + RBAC middleware tests for workflows app."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from workflows.config import settings
from workflows.models.auth import AuthEvent


def _csrf(cookies) -> str:
    return cookies.get(f"{settings.auth_cookie_name}_csrf", "")


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
        data={"email": "newuser@example.com", "role": "manager", "csrf_token": _csrf(owner_login.cookies)},
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
        data={"email": "ops@example.com", "role": "manager", "csrf_token": _csrf(owner_login.cookies)},
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
        data={"email": "ops@example.com", "role": "manager", "is_active": "false", "csrf_token": _csrf(owner_login.cookies)},
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
    assert "Invalid credentials" in disabled_login.text

    reject_disable_owner = await client.post(
        "/auth/users",
        data={"email": "owner@example.com", "role": "owner", "is_active": "false", "csrf_token": _csrf(owner_login.cookies)},
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
        data={"email": "owner@example.com", "password": "ownerpass123", "next": "/"},
        follow_redirects=False,
    )
    assert owner1_login.status_code == 303

    invite_resp = await client.post(
        "/auth/invites",
        data={"email": "owner2@example.com", "role": "owner", "csrf_token": _csrf(owner1_login.cookies)},
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
        data={"email": "owner2@example.com", "password": "owner2pass123", "next": "/"},
        follow_redirects=False,
    )
    assert owner2_login.status_code == 303

    disable_owner1 = await client.post(
        "/auth/users",
        data={"email": "owner@example.com", "role": "owner", "is_active": "false", "csrf_token": _csrf(owner2_login.cookies)},
        cookies=owner2_login.cookies,
        follow_redirects=False,
    )
    assert disable_owner1.status_code == 303
    assert disable_owner1.headers["location"].startswith("/auth/users?msg=User+updated")

    owner1_disabled_login = await client.post(
        "/auth/login",
        data={"email": "owner@example.com", "password": "ownerpass123", "next": "/"},
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
        data={"email": "owner@example.com", "password": "ownerpass123", "next": "/"},
        follow_redirects=False,
    )
    assert owner_login.status_code == 303

    invite_resp = await client.post(
        "/auth/invites",
        data={"email": "manager@example.com", "role": "manager", "csrf_token": _csrf(owner_login.cookies)},
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
        data={"email": "manager@example.com", "password": "managerpass123", "next": "/"},
        follow_redirects=False,
    )
    assert manager_login.status_code == 303

    reject_owner_change = await client.post(
        "/auth/users",
        data={"email": "owner@example.com", "role": "manager", "is_active": "true", "csrf_token": _csrf(manager_login.cookies)},
        cookies=manager_login.cookies,
        follow_redirects=False,
    )
    assert reject_owner_change.status_code == 303
    assert reject_owner_change.headers["location"].startswith("/auth/users?msg=Update+rejected")

    reject_self_escalate = await client.post(
        "/auth/users",
        data={"email": "manager@example.com", "role": "owner", "is_active": "true", "csrf_token": _csrf(manager_login.cookies)},
        cookies=manager_login.cookies,
        follow_redirects=False,
    )
    assert reject_self_escalate.status_code == 303
    assert reject_self_escalate.headers["location"].startswith("/auth/users?msg=Update+rejected")

    owner_relogin = await client.post(
        "/auth/login",
        data={"email": "owner@example.com", "password": "ownerpass123", "next": "/"},
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
        data={"email": "owner@example.com", "password": "ownerpass123", "next": "/"},
        follow_redirects=False,
    )
    assert owner_login.status_code == 303

    changed = await client.post(
        "/auth/password",
        data={
            "current_password": "ownerpass123",
            "new_password": "ownerpass456",
            "confirm_password": "ownerpass456",
            "csrf_token": _csrf(owner_login.cookies),
        },
        cookies=owner_login.cookies,
        follow_redirects=False,
    )
    assert changed.status_code == 303
    assert changed.headers["location"].startswith("/auth/password?msg=Password+updated")

    old_login = await client.post(
        "/auth/login",
        data={"email": "owner@example.com", "password": "ownerpass123", "next": "/"},
        follow_redirects=False,
    )
    assert old_login.status_code == 200
    assert "Invalid credentials" in old_login.text

    new_login = await client.post(
        "/auth/login",
        data={"email": "owner@example.com", "password": "ownerpass456", "next": "/"},
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
        data={"email": "owner@example.com", "password": "ownerpass123", "next": "/"},
        follow_redirects=False,
    )
    assert owner_login.status_code == 303

    rejected = await client.post(
        "/auth/password",
        data={
            "current_password": "wrongpass",
            "new_password": "ownerpass456",
            "confirm_password": "ownerpass456",
            "csrf_token": _csrf(owner_login.cookies),
        },
        cookies=owner_login.cookies,
        follow_redirects=False,
    )
    assert rejected.status_code == 303
    assert rejected.headers["location"].startswith("/auth/password?msg=Current+password+invalid")


@pytest.mark.asyncio
async def test_login_rate_limit_blocks_retries(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "auth_secret", "test-secret")
    monkeypatch.setattr(settings, "auth_bootstrap_email", "owner@example.com")
    monkeypatch.setattr(settings, "auth_bootstrap_password", "ownerpass123")
    monkeypatch.setattr(settings, "auth_bootstrap_role", "owner")
    monkeypatch.setattr(settings, "auth_rate_limit_window_seconds", 60)
    monkeypatch.setattr(settings, "auth_rate_limit_max_attempts", 2)
    monkeypatch.setattr(settings, "auth_rate_limit_block_seconds", 60)

    first = await client.post(
        "/auth/login",
        data={"email": "ghost@example.com", "password": "wrong-pass", "next": "/"},
        follow_redirects=False,
    )
    assert first.status_code == 200
    assert "Invalid credentials" in first.text

    second = await client.post(
        "/auth/login",
        data={"email": "ghost@example.com", "password": "wrong-pass", "next": "/"},
        follow_redirects=False,
    )
    assert second.status_code == 429
    assert "Too many login attempts" in second.text

    blocked_valid = await client.post(
        "/auth/login",
        data={"email": "ghost@example.com", "password": "ownerpass123", "next": "/"},
        follow_redirects=False,
    )
    assert blocked_valid.status_code == 429
    assert "Too many login attempts" in blocked_valid.text


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
        data={"email": "owner@example.com", "password": "ownerpass123", "next": "/"},
        follow_redirects=False,
    )
    assert owner_login.status_code == 303

    invite_resp = await client.post(
        "/auth/invites",
        data={"email": "agent@example.com", "role": "manager", "csrf_token": _csrf(owner_login.cookies)},
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
        data={"email": "agent@example.com", "password": "agentpass123", "next": "/"},
        follow_redirects=False,
    )
    assert agent_login.status_code == 303

    disable_agent = await client.post(
        "/auth/users",
        data={"email": "agent@example.com", "role": "manager", "is_active": "false", "csrf_token": _csrf(owner_login.cookies)},
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
        data={"email": "owner@example.com", "password": "ownerpass123", "next": "/"},
        follow_redirects=False,
    )
    assert owner_login.status_code == 303

    invite_resp = await client.post(
        "/auth/invites",
        data={"email": "manager2@example.com", "role": "manager", "csrf_token": _csrf(owner_login.cookies)},
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
        data={"email": "manager2@example.com", "password": "manager2pass123", "next": "/"},
        follow_redirects=False,
    )
    assert manager_login.status_code == 303

    demote_manager = await client.post(
        "/auth/users",
        data={"email": "manager2@example.com", "role": "viewer", "is_active": "true", "csrf_token": _csrf(owner_login.cookies)},
        cookies=owner_login.cookies,
        follow_redirects=False,
    )
    assert demote_manager.status_code == 303
    assert demote_manager.headers["location"].startswith("/auth/users?msg=User+updated")

    manager_invite_attempt = await client.post(
        "/auth/invites",
        data={"email": "shouldfail@example.com", "role": "viewer", "csrf_token": _csrf(manager_login.cookies)},
        cookies=manager_login.cookies,
        follow_redirects=False,
    )
    assert manager_invite_attempt.status_code == 303
    assert manager_invite_attempt.headers["location"].startswith("/auth/login")


@pytest.mark.asyncio
async def test_csrf_required_for_invite_creation(
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

    rejected = await client.post(
        "/auth/invites",
        data={"email": "csrf-test@example.com", "role": "viewer"},
        cookies=owner_login.cookies,
        follow_redirects=False,
    )
    assert rejected.status_code == 303
    assert rejected.headers["location"].startswith("/auth/invites?msg=Invalid+request")


@pytest.mark.asyncio
async def test_login_rejects_scheme_relative_next_redirect(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "auth_secret", "test-secret")
    monkeypatch.setattr(settings, "auth_bootstrap_email", "owner@example.com")
    monkeypatch.setattr(settings, "auth_bootstrap_password", "ownerpass123")
    monkeypatch.setattr(settings, "auth_bootstrap_role", "owner")

    login = await client.post(
        "/auth/login",
        data={"email": "owner@example.com", "password": "ownerpass123", "next": "//evil.example/path"},
        follow_redirects=False,
    )
    assert login.status_code == 303
    assert login.headers["location"] == "/"


@pytest.mark.asyncio
async def test_login_page_rejects_scheme_relative_next_when_already_authenticated(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "auth_secret", "test-secret")
    monkeypatch.setattr(settings, "auth_bootstrap_email", "owner@example.com")
    monkeypatch.setattr(settings, "auth_bootstrap_password", "ownerpass123")
    monkeypatch.setattr(settings, "auth_bootstrap_role", "owner")

    login = await client.post(
        "/auth/login",
        data={"email": "owner@example.com", "password": "ownerpass123", "next": "/"},
        follow_redirects=False,
    )
    assert login.status_code == 303

    redirect = await client.get(
        "/auth/login",
        params={"next": "//evil.example/path"},
        cookies=login.cookies,
        follow_redirects=False,
    )
    assert redirect.status_code == 303
    assert redirect.headers["location"] == "/"


@pytest.mark.asyncio
async def test_csrf_required_for_login_and_invite_accept(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "auth_secret", "test-secret")
    monkeypatch.setattr(settings, "auth_bootstrap_email", "owner@example.com")
    monkeypatch.setattr(settings, "auth_bootstrap_password", "ownerpass123")
    monkeypatch.setattr(settings, "auth_bootstrap_role", "owner")

    login_rejected = await client.request(
        "POST",
        "/auth/login",
        data={"email": "owner@example.com", "password": "ownerpass123", "next": "/"},
        follow_redirects=False,
    )
    assert login_rejected.status_code == 400
    assert "Invalid request" in login_rejected.text

    owner_login = await client.post(
        "/auth/login",
        data={"email": "owner@example.com", "password": "ownerpass123", "next": "/"},
        follow_redirects=False,
    )
    assert owner_login.status_code == 303

    invite_resp = await client.post(
        "/auth/invites",
        data={
            "email": "accept-csrf@example.com",
            "role": "manager",
            "csrf_token": _csrf(owner_login.cookies),
        },
        cookies=owner_login.cookies,
        follow_redirects=False,
    )
    token = parse_qs(urlparse(invite_resp.headers["location"]).query).get("token", [""])[0]
    assert token

    accept_rejected = await client.request(
        "POST",
        "/auth/accept",
        data={"token": token, "password": "acceptpass123"},
        follow_redirects=False,
    )
    assert accept_rejected.status_code == 400
    assert "Invalid request" in accept_rejected.text


@pytest.mark.asyncio
async def test_auth_audit_events_cover_core_flows(
    client: AsyncClient,
    db,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "auth_secret", "test-secret")
    monkeypatch.setattr(settings, "auth_bootstrap_email", "owner@example.com")
    monkeypatch.setattr(settings, "auth_bootstrap_password", "ownerpass123")
    monkeypatch.setattr(settings, "auth_bootstrap_role", "owner")

    failed_login = await client.post(
        "/auth/login",
        data={"email": "owner@example.com", "password": "wrong-pass", "next": "/"},
        follow_redirects=False,
    )
    assert failed_login.status_code == 200
    assert "Invalid credentials" in failed_login.text

    owner_login = await client.post(
        "/auth/login",
        data={"email": "owner@example.com", "password": "ownerpass123", "next": "/"},
        follow_redirects=False,
    )
    assert owner_login.status_code == 303

    invite_resp = await client.post(
        "/auth/invites",
        data={
            "email": "audit-user@example.com",
            "role": "manager",
            "csrf_token": _csrf(owner_login.cookies),
        },
        cookies=owner_login.cookies,
        follow_redirects=False,
    )
    token = parse_qs(urlparse(invite_resp.headers["location"]).query).get("token", [""])[0]
    assert token

    accept_resp = await client.post(
        "/auth/accept",
        data={"token": token, "password": "auditpass123"},
        follow_redirects=False,
    )
    assert accept_resp.status_code == 303

    update_resp = await client.post(
        "/auth/users",
        data={
            "email": "audit-user@example.com",
            "role": "viewer",
            "is_active": "true",
            "csrf_token": _csrf(owner_login.cookies),
        },
        cookies=owner_login.cookies,
        follow_redirects=False,
    )
    assert update_resp.status_code == 303

    pw_resp = await client.post(
        "/auth/password",
        data={
            "current_password": "ownerpass123",
            "new_password": "ownerpass456",
            "confirm_password": "ownerpass456",
            "csrf_token": _csrf(owner_login.cookies),
        },
        cookies=owner_login.cookies,
        follow_redirects=False,
    )
    assert pw_resp.status_code == 303
    assert pw_resp.headers["location"].startswith("/auth/password?msg=Password+updated")

    rows = (
        await db.execute(
            select(AuthEvent.action, AuthEvent.outcome).order_by(AuthEvent.created_at.asc())
        )
    ).all()
    action_outcomes = {(row[0], row[1]) for row in rows}
    assert ("login", "failure") in action_outcomes
    assert ("login", "success") in action_outcomes
    assert ("invite_create", "success") in action_outcomes
    assert ("invite_accept", "success") in action_outcomes
    assert ("user_update", "success") in action_outcomes
    assert ("password_change", "success") in action_outcomes
