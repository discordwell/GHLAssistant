"""Webhook validation helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Mapping

from fastapi import HTTPException, Request

from ..config import settings


def _twilio_expected_signature(url: str, params: Mapping[str, str], auth_token: str) -> str:
    """Generate the expected Twilio signature."""
    payload = url + "".join(f"{k}{params[k]}" for k in sorted(params.keys()))
    digest = hmac.new(
        auth_token.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


def verify_twilio_signature(request: Request, form_data: Mapping[str, str]) -> None:
    """Verify Twilio webhook signature when configured."""
    if not settings.webhooks_verify_twilio_signature:
        return

    auth_token = settings.twilio_auth_token
    if not auth_token:
        return

    provided = request.headers.get("x-twilio-signature", "").strip()
    if not provided:
        raise HTTPException(status_code=401, detail="Missing Twilio signature")

    expected = _twilio_expected_signature(str(request.url), form_data, auth_token)
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Invalid Twilio signature")


def verify_sendgrid_inbound_auth(request: Request) -> None:
    """Verify SendGrid inbound parse auth token/basic auth when configured."""
    token = settings.sendgrid_inbound_token
    basic_user = settings.sendgrid_inbound_basic_user
    basic_pass = settings.sendgrid_inbound_basic_pass

    # Token-based auth (query param or header).
    if token:
        provided = (
            request.query_params.get("token", "").strip()
            or request.headers.get("x-sendgrid-token", "").strip()
            or request.headers.get("x-api-key", "").strip()
        )
        if not provided or not hmac.compare_digest(provided, token):
            raise HTTPException(status_code=401, detail="Invalid SendGrid inbound token")

    # HTTP Basic auth (optional).
    if basic_user or basic_pass:
        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("basic "):
            raise HTTPException(status_code=401, detail="Missing SendGrid basic auth")
        try:
            raw = base64.b64decode(auth[6:].strip()).decode("utf-8")
            username, password = raw.split(":", 1)
        except Exception as exc:  # pragma: no cover - defensive parsing path
            raise HTTPException(status_code=401, detail="Malformed SendGrid basic auth") from exc

        if basic_user and not hmac.compare_digest(username, basic_user):
            raise HTTPException(status_code=401, detail="Invalid SendGrid username")
        if basic_pass and not hmac.compare_digest(password, basic_pass):
            raise HTTPException(status_code=401, detail="Invalid SendGrid password")

