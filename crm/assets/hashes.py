"""Small hashing helpers for assets.

We use fixed-size sha256 hex strings for:
- stable identity keys (avoid indexing large TEXT payloads in Postgres)
- URL/job de-duplication keys
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any


def sha256_hex_text(value: str) -> str:
    if not isinstance(value, str):
        value = str(value)
    return hashlib.sha256(value.encode("utf-8", "surrogatepass")).hexdigest()


def asset_ref_identity_sha256(
    *,
    entity_type: str,
    entity_id: uuid.UUID | None,
    remote_entity_id: str | None,
    field_path: str | None,
    usage: str | None,
    original_url: str | None,
) -> str:
    """Compute a stable identity hash for an AssetRef.

    Note: We normalize None -> "" so idempotency is stable across DBs.
    """
    parts: list[str] = [
        (entity_type or "").strip(),
        str(entity_id) if entity_id else "",
        (remote_entity_id or "").strip(),
        (field_path or "").strip(),
        (usage or "").strip(),
        (original_url or "").strip(),
    ]
    # Use an unambiguous separator to avoid accidental concatenation collisions.
    return sha256_hex_text("\x1f".join(parts))


def url_sha256(url: str) -> str:
    """Hash a URL string for uniqueness/indexing."""
    if not isinstance(url, str):
        url = str(url)
    return sha256_hex_text(url.strip())


def safe_str(value: Any) -> str:
    """Convert to string without throwing, best-effort."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return str(value)
    except Exception:
        return ""

