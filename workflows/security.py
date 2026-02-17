"""Security helpers for chat and webhook endpoints."""

from __future__ import annotations

import hashlib
import hmac
import time

from fastapi import HTTPException, Request

from .config import settings


def _extract_token(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()

    return (
        request.headers.get("x-api-key", "").strip()
        or request.headers.get("x-workflow-api-key", "").strip()
        or request.headers.get("x-chat-api-key", "").strip()
    )


def require_chat_api_key(request: Request) -> None:
    """Enforce chat endpoint key auth when configured."""
    expected = settings.chat_api_key.strip()
    if not expected:
        return

    provided = _extract_token(request)
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Invalid chat API key")


def verify_webhook_request(request: Request, body: bytes) -> None:
    """Verify webhook auth using HMAC signature or API key."""
    signing_secret = settings.webhook_signing_secret.strip()
    api_key = settings.webhook_api_key.strip()

    # Prefer HMAC verification when configured.
    if signing_secret:
        timestamp_raw = request.headers.get("x-webhook-timestamp", "").strip()
        signature_raw = request.headers.get("x-webhook-signature", "").strip()
        if not timestamp_raw or not signature_raw:
            raise HTTPException(status_code=401, detail="Missing webhook signature headers")

        try:
            timestamp = int(timestamp_raw)
        except ValueError as exc:
            raise HTTPException(status_code=401, detail="Invalid webhook timestamp") from exc

        now = int(time.time())
        if abs(now - timestamp) > settings.webhook_signature_ttl_seconds:
            raise HTTPException(status_code=401, detail="Webhook signature expired")

        body_text = body.decode("utf-8", errors="replace")
        message = f"{timestamp}.{body_text}".encode("utf-8")
        expected = hmac.new(signing_secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
        provided = signature_raw
        if provided.startswith("sha256="):
            provided = provided.split("=", 1)[1]

        if not hmac.compare_digest(provided, expected):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
        return

    # Fallback: API key if configured.
    if api_key:
        provided = _extract_token(request)
        if not provided or not hmac.compare_digest(provided, api_key):
            raise HTTPException(status_code=401, detail="Invalid webhook API key")

