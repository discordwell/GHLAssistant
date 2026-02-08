"""Raw sync archive helpers for loss-minimizing imports/exports."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _archive_root() -> Path:
    # /.../crm/sync/archive.py -> project root is parents[2]
    return Path(__file__).resolve().parents[2] / "data" / "sync_archives"


def write_sync_archive(location_key: str, domain: str, payload: Any) -> Path | None:
    """Persist a raw sync payload to disk.

    Best effort: returns None when archiving fails.
    """
    try:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safe_location = "".join(ch for ch in location_key if ch.isalnum() or ch in ("-", "_")) or "unknown"
        safe_domain = "".join(ch for ch in domain if ch.isalnum() or ch in ("-", "_")) or "domain"

        out_dir = _archive_root() / safe_location
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{ts}_{safe_domain}.json"

        with out_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False, default=str)

        return out_path
    except Exception:
        return None
