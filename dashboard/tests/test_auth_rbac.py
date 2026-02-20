"""Dashboard auth tests against CRM-backed auth store."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from maxlevel.platform_auth import hash_password

from dashboard.config import settings


def _csrf(cookies) -> str:
    return cookies.get(f"{settings.auth_cookie_name}_csrf", "")


async def _insert_account(
    seeded_db,
    *,
    email: str,
    password: str,
    role: str = "owner",
    is_active: bool = True,
):
    async with seeded_db.crm_session() as session:
        await session.execute(
            text(
                """
                INSERT INTO auth_account (
                    id, email, password_hash, role, is_active,
                    invited_by_email, last_login_at, created_at, updated_at
                )
                VALUES (
                    :id, :email, :password_hash, :role, :is_active,
                    :invited_by_email, :last_login_at, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "email": email,
                "password_hash": hash_password(password),
                "role": role,
                "is_active": is_active,
                "invited_by_email": None,
                "last_login_at": None,
            },
        )
        await session.commit()


@pytest.mark.asyncio
async def test_dashboard_login_uses_persistent_crm_account(client, seeded_db, monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "auth_secret", "dash-test-secret")

    await _insert_account(
        seeded_db,
        email="dashowner@example.com",
        password="ownerpass123",
        role="owner",
    )

    login_page = await client.get("/auth/login", params={"next": "/"}, follow_redirects=False)
    assert login_page.status_code == 200

    login = await client.post(
        "/auth/login",
        data={
            "email": "dashowner@example.com",
            "password": "ownerpass123",
            "next": "/",
            "csrf_token": _csrf(login_page.cookies),
        },
        cookies=login_page.cookies,
        follow_redirects=False,
    )
    assert login.status_code == 303
    assert login.headers["location"] == "/"

    home = await client.get("/", cookies=login.cookies, follow_redirects=False)
    assert home.status_code == 200


@pytest.mark.asyncio
async def test_dashboard_login_rejects_bootstrap_without_db_account(client, monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "auth_secret", "dash-test-secret")
    monkeypatch.setattr(settings, "auth_bootstrap_email", "bootstrap@example.com")
    monkeypatch.setattr(settings, "auth_bootstrap_password", "bootstrap-pass")
    monkeypatch.setattr(settings, "auth_bootstrap_role", "owner")

    login_page = await client.get("/auth/login", params={"next": "/"}, follow_redirects=False)
    assert login_page.status_code == 200

    login = await client.post(
        "/auth/login",
        data={
            "email": "bootstrap@example.com",
            "password": "bootstrap-pass",
            "next": "/",
            "csrf_token": _csrf(login_page.cookies),
        },
        cookies=login_page.cookies,
        follow_redirects=False,
    )
    assert login.status_code == 200
    assert "Invalid credentials" in login.text


@pytest.mark.asyncio
async def test_dashboard_login_requires_csrf(client, seeded_db, monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "auth_secret", "dash-test-secret")

    await _insert_account(
        seeded_db,
        email="dashcsrf@example.com",
        password="ownerpass123",
        role="owner",
    )

    rejected = await client.post(
        "/auth/login",
        data={"email": "dashcsrf@example.com", "password": "ownerpass123", "next": "/"},
        follow_redirects=False,
    )
    assert rejected.status_code == 400
    assert "Invalid request" in rejected.text


@pytest.mark.asyncio
async def test_dashboard_login_writes_auth_audit_events(client, seeded_db, monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "auth_secret", "dash-test-secret")

    await _insert_account(
        seeded_db,
        email="dashaudit@example.com",
        password="ownerpass123",
        role="owner",
    )

    bad_page = await client.get("/auth/login", params={"next": "/"}, follow_redirects=False)
    bad_login = await client.post(
        "/auth/login",
        data={
            "email": "dashaudit@example.com",
            "password": "wrong-pass",
            "next": "/",
            "csrf_token": _csrf(bad_page.cookies),
        },
        cookies=bad_page.cookies,
        follow_redirects=False,
    )
    assert bad_login.status_code == 200

    ok_page = await client.get("/auth/login", params={"next": "/"}, follow_redirects=False)
    ok_login = await client.post(
        "/auth/login",
        data={
            "email": "dashaudit@example.com",
            "password": "ownerpass123",
            "next": "/",
            "csrf_token": _csrf(ok_page.cookies),
        },
        cookies=ok_page.cookies,
        follow_redirects=False,
    )
    assert ok_login.status_code == 303

    async with seeded_db.crm_session() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT action, outcome FROM auth_event WHERE action = 'login' ORDER BY created_at ASC"
                )
            )
        ).all()
    action_outcomes = {(row[0], row[1]) for row in rows}
    assert ("login", "failure") in action_outcomes
    assert ("login", "success") in action_outcomes
