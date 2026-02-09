"""Media Library (files) API.

GHL does not expose a stable public API for Media Library in all accounts.
This module is best-effort and supports multiple internal endpoint variants.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, TYPE_CHECKING
from urllib.parse import urlparse, parse_qsl

import httpx

if TYPE_CHECKING:
    from .client import GHLClient


def _extract_list_payload(resp: dict[str, Any]) -> list[dict[str, Any]]:
    """Best-effort extraction of file items from varied response shapes."""
    if not isinstance(resp, dict):
        return []

    # Common keys first.
    for key in ("files", "media", "medias", "items", "data", "results"):
        value = resp.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict) and isinstance(value.get(key), list):
            nested = value.get(key)
            return [item for item in nested if isinstance(item, dict)]

    # Fallback: first top-level list-of-dicts value.
    for value in resp.values():
        if isinstance(value, list) and value and all(isinstance(i, dict) for i in value):
            return value  # type: ignore[return-value]

    return []


def _looks_like_media_file(item: dict[str, Any]) -> bool:
    if not isinstance(item, dict) or not item:
        return False
    for key in ("url", "fileUrl", "publicUrl", "downloadUrl", "thumbnailUrl", "previewUrl"):
        v = item.get(key)
        if isinstance(v, str) and v.strip().lower().startswith(("http://", "https://")):
            return True
    for key in ("name", "fileName", "filename", "originalName", "contentType", "mimeType"):
        v = item.get(key)
        if isinstance(v, str) and v.strip():
            return True
    return False


def _session_logs_dir() -> Path | None:
    """Best-effort locate repo-local network logs (gitignored)."""
    # Running from repo: <root>/src/maxlevel/api/media_library.py
    try:
        root = Path(__file__).resolve().parents[3]
        candidate = root / "data" / "network_logs"
        if candidate.is_dir():
            return candidate
    except Exception:
        pass

    # Fallback: relative to CWD.
    try:
        candidate = Path.cwd() / "data" / "network_logs"
        if candidate.is_dir():
            return candidate
    except Exception:
        pass

    return None


def _discover_endpoint_from_recent_sessions() -> tuple[str, dict[str, Any]] | None:
    """Discover a likely media-library listing endpoint from recent session logs."""
    log_dir = _session_logs_dir()
    if not log_dir:
        return None

    sessions = sorted(
        log_dir.glob("session_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:5]
    if not sessions:
        return None

    for path in sessions:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        calls = data.get("api_calls", [])
        if not isinstance(calls, list):
            continue

        for call in calls:
            if not isinstance(call, dict):
                continue
            if (call.get("method") or "").upper() != "GET":
                continue
            if call.get("response_status") != 200:
                continue
            if call.get("response_body_truncated") or call.get("response_body_base64"):
                continue
            url = call.get("url")
            body = call.get("response_body")
            if not (isinstance(url, str) and isinstance(body, str) and body.strip()):
                continue

            # Fast prefilter: avoid parsing every JSON body.
            if "http" not in body and "url" not in body.lower():
                continue

            try:
                payload = json.loads(body)
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue

            items = _extract_list_payload(payload)
            if not items:
                continue
            if not any(_looks_like_media_file(it) for it in items[:20]):
                continue

            try:
                parsed = urlparse(url)
            except Exception:
                continue
            if not parsed.path:
                continue

            params: dict[str, Any] = {}
            for k, v in parse_qsl(parsed.query, keep_blank_values=True):
                if not k:
                    continue
                # Keep last value (GHL usually uses single-value params).
                params[k] = v

            return parsed.path, params

    return None


class MediaLibraryAPI:
    """Best-effort internal Media Library listing."""

    def __init__(self, client: "GHLClient"):
        self._client = client
        self._discovered: tuple[str, dict[str, Any]] | None = None

    @property
    def _location_id(self) -> str:
        lid = self._client.config.location_id
        if not lid:
            raise ValueError("location_id required")
        return lid

    def _candidate_endpoints(self, *, location_id: str) -> list[str]:
        override = os.environ.get("MAXLEVEL_MEDIA_LIBRARY_ENDPOINT")
        endpoints: list[str] = []
        if isinstance(override, str) and override.strip():
            endpoints.append(override.strip())

        # Prefer session-log discovery when available (most stable across accounts).
        if self._discovered is None:
            self._discovered = _discover_endpoint_from_recent_sessions()
        if self._discovered:
            endpoints.append(self._discovered[0])

        # These are guessed/internal variants observed across accounts.
        # We try multiple to reduce brittleness.
        endpoints.extend(
            [
                "/medias/files",
                "/medias/files/",
                "/media/files",
                "/media/files/",
                "/medias",
                "/medias/",
                f"/locations/{location_id}/medias/files",
                f"/locations/{location_id}/medias",
                f"/locations/{location_id}/media/files",
                f"/locations/{location_id}/media",
                f"/locations/{location_id}/files",
            ]
        )
        return endpoints

    async def list_files(
        self,
        *,
        location_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
        folder_id: str | None = None,
    ) -> dict[str, Any]:
        """List media files (best-effort).

        Returns the raw JSON response (shape varies).
        """
        lid = location_id or self._location_id

        base_params: dict[str, Any] = {
            "locationId": lid,
            "limit": int(limit),
            "offset": int(offset),
        }
        if isinstance(folder_id, str) and folder_id:
            base_params["folderId"] = folder_id

        last_err: Exception | None = None
        for endpoint in self._candidate_endpoints(location_id=lid):
            try:
                params = dict(base_params)
                # Merge in discovered params if the endpoint came from session logs.
                if self._discovered and endpoint == self._discovered[0]:
                    params = {**self._discovered[1], **params}
                return await self._client._get(endpoint, **params)
            except httpx.HTTPStatusError as e:
                last_err = e
                status = e.response.status_code if e.response else None
                # 404/405 indicate wrong endpoint; keep probing.
                if status in {404, 405}:
                    continue
                raise
            except Exception as e:
                last_err = e
                continue

        raise RuntimeError(f"Media library endpoint probe failed: {last_err}")

    async def list_all_files(
        self,
        *,
        location_id: str | None = None,
        page_size: int = 200,
        max_pages: int = 1000,
    ) -> list[dict[str, Any]]:
        """Fetch all media files using limit/offset pagination (best-effort)."""
        lid = location_id or self._location_id

        all_items: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        offset = 0

        for _ in range(max_pages):
            resp = await self.list_files(location_id=lid, limit=page_size, offset=offset)
            items = _extract_list_payload(resp)
            if not items:
                break

            new_count = 0
            for item in items:
                raw_id = item.get("id") or item.get("_id") or item.get("fileId") or item.get("mediaId")
                item_id = raw_id if isinstance(raw_id, str) else ""
                if item_id:
                    if item_id in seen_ids:
                        continue
                    seen_ids.add(item_id)
                all_items.append(item)
                new_count += 1

            if new_count == 0:
                break

            if len(items) < page_size:
                break

            offset += len(items)

        return all_items
