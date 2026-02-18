"""Security behavior tests for workflows endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from workflows.config import settings
from workflows.services import step_svc, workflow_svc


@pytest.mark.asyncio
async def test_webhook_api_key_enforced_when_configured(
    client: AsyncClient,
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    wf = await workflow_svc.create_workflow(db, name="Secure Webhook", trigger_type="webhook")
    await workflow_svc.publish_workflow(db, wf.id)
    await step_svc.create_step(db, wf.id, step_type="delay", config={"seconds": 0})

    monkeypatch.setattr(settings, "webhook_api_key", "top-secret")

    denied = await client.post(f"/webhooks/{wf.id}", json={"ok": True})
    assert denied.status_code == 401

    allowed = await client.post(
        f"/webhooks/{wf.id}",
        json={"ok": True},
        headers={"X-API-Key": "top-secret"},
    )
    assert allowed.status_code == 200


@pytest.mark.asyncio
async def test_chat_api_key_enforced_when_configured(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "chat_api_key", "chat-secret")

    denied = await client.post("/chat/send", json={"messages": []})
    assert denied.status_code == 401


@pytest.mark.asyncio
async def test_webhook_fails_closed_without_auth_when_enabled(
    client: AsyncClient,
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    wf = await workflow_svc.create_workflow(db, name="Fail Closed Webhook", trigger_type="webhook")
    await workflow_svc.publish_workflow(db, wf.id)
    await step_svc.create_step(db, wf.id, step_type="delay", config={"seconds": 0})

    monkeypatch.setattr(settings, "security_fail_closed", True)
    monkeypatch.setattr(settings, "webhook_api_key", "")
    monkeypatch.setattr(settings, "webhook_signing_secret", "")

    resp = await client.post(f"/webhooks/{wf.id}", json={"ok": True})
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_chat_fails_closed_without_api_key_when_enabled(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "security_fail_closed", True)
    monkeypatch.setattr(settings, "chat_api_key", "")

    resp = await client.post("/chat/send", json={"messages": []})
    assert resp.status_code == 503
