"""Webhook security tests for CRM callbacks."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from crm.config import settings


@pytest.mark.asyncio
async def test_twilio_signature_required_when_token_configured(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "twilio_auth_token", "token123")
    monkeypatch.setattr(settings, "webhooks_verify_twilio_signature", True)

    resp = await client.post("/webhooks/twilio/status", data={"MessageSid": "SM123"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_sendgrid_token_required_when_configured(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "sendgrid_inbound_token", "sg-secret")

    resp = await client.post("/webhooks/sendgrid/inbound", data={"from": "test@example.com"})
    assert resp.status_code == 401

