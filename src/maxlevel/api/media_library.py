"""Media Library (files) API.

GHL does not expose a stable public API for Media Library in all accounts.
This module is best-effort and supports multiple internal endpoint variants.
"""

from __future__ import annotations

import json
import mimetypes
import os
from pathlib import Path
from typing import Any, TYPE_CHECKING
from urllib.parse import urlparse, parse_qsl

import httpx

if TYPE_CHECKING:
    from .client import GHLClient


SERVICES_BASE_URL = "https://services.leadconnectorhq.com"


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
    def _token_id(self) -> str | None:
        tok = self._client.config.token_id
        if not isinstance(tok, str):
            return None
        tok = tok.strip()
        return tok or None

    @property
    def _location_id(self) -> str:
        lid = self._client.config.location_id
        if not lid:
            raise ValueError("location_id required")
        return lid

    def _services_base_url(self) -> str:
        override = os.environ.get("MAXLEVEL_SERVICES_BASE_URL")
        if isinstance(override, str) and override.strip().lower().startswith(("http://", "https://")):
            return override.strip().rstrip("/")
        return SERVICES_BASE_URL

    def _services_headers(self) -> dict[str, str]:
        token_id = self._token_id
        if not token_id:
            raise RuntimeError(
                "token_id missing (required for services.* Media Library endpoints). "
                "Capture a browser session and load config via GHLConfig.from_session_file()."
            )

        # services.leadconnectorhq.com uses token-id (Firebase ID token) instead of
        # Authorization Bearer for some endpoints.
        return {
            "token-id": token_id,
            "Accept": "application/json, text/plain, */*",
            **self._client.REQUIRED_HEADERS,
        }

    def _require_http_client(self) -> httpx.AsyncClient:
        if not getattr(self._client, "_client", None):
            raise RuntimeError("Client not initialized. Use 'async with' context.")
        return self._client._client  # type: ignore[return-value]

    async def _services_get_json(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        client = self._require_http_client()
        url = f"{self._services_base_url()}{path}"
        resp = await client.get(url, params=params or {}, headers=self._services_headers())
        resp.raise_for_status()
        return resp.json()

    async def _services_post_json(self, path: str, *, data: dict[str, Any] | None = None) -> dict[str, Any]:
        client = self._require_http_client()
        url = f"{self._services_base_url()}{path}"
        headers = dict(self._services_headers())
        headers["Content-Type"] = "application/json"
        resp = await client.post(url, json=data or {}, headers=headers)
        resp.raise_for_status()
        return resp.json()

    async def list_files_services(
        self,
        *,
        location_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
        folder_id: str | None = None,
        mode: str = "public",
        type: str = "file",
        query: str = "",
        sort_by: str = "updatedAt",
        sort_order: str = "desc",
    ) -> dict[str, Any]:
        """List media files using services.leadconnectorhq.com endpoints.

        This path tends to be the most stable across accounts, but requires
        a `token-id` captured from browser traffic.
        """
        lid = location_id or self._location_id
        params: dict[str, Any] = {
            "altId": lid,
            "altType": "location",
            "parentId": (folder_id or ""),
            "query": (query or ""),
            "type": (type or "file"),
            "sortBy": (sort_by or "updatedAt"),
            "sortOrder": (sort_order or "desc"),
            "mode": (mode or "public"),
            "offset": int(offset),
            "limit": int(limit),
        }
        return await self._services_get_json("/medias/files/", params=params)

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

        # Prefer services endpoint when we have token-id (more reliable than probing).
        if self._token_id:
            try:
                return await self.list_files_services(
                    location_id=lid,
                    limit=limit,
                    offset=offset,
                    folder_id=folder_id,
                )
            except Exception:
                # Fall back to internal backend endpoints (best-effort).
                pass

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

    async def upload_bytes(
        self,
        *,
        filename: str,
        content_type: str,
        data: bytes,
        location_id: str | None = None,
        folder_id: str | None = None,
        mode: str = "public",
    ) -> dict[str, Any]:
        """Upload bytes to Media Library via services endpoints (create -> PUT -> verify)."""
        lid = location_id or self._location_id
        name = (filename or "").strip() or "upload.bin"
        ct = (content_type or "").strip() or "application/octet-stream"
        parent_id = (folder_id or "").strip()
        size = len(data or b"")

        # 1) Create an upload, get signed PUT URL.
        created = await self._services_post_json(
            "/medias/files/",
            data={
                "name": name,
                "contentType": ct,
                "parentId": parent_id,
                "altType": "location",
                "altId": lid,
                "size": int(size),
                "mode": mode,
            },
        )
        signed_url = created.get("url")
        file_id = created.get("aknId") or created.get("_id") or created.get("id")
        if not isinstance(signed_url, str) or not signed_url.strip():
            raise RuntimeError(f"Media create did not return signed url (keys={list(created.keys())})")
        if not isinstance(file_id, str) or not file_id.strip():
            raise RuntimeError(f"Media create did not return file id (keys={list(created.keys())})")

        # 2) Upload bytes to signed URL (GCS).
        async with httpx.AsyncClient(timeout=60.0) as raw:
            put = await raw.put(signed_url, content=data or b"", headers={"Content-Type": ct})
            put.raise_for_status()

        # 3) Verify and return the resolved media object.
        verified = await self._services_post_json(
            "/medias/files/verify",
            data={
                "altId": lid,
                "altType": "location",
                "id": file_id,
                "mode": mode,
            },
        )
        return verified

    async def upload_path(
        self,
        *,
        path: str | Path,
        filename: str | None = None,
        content_type: str | None = None,
        location_id: str | None = None,
        folder_id: str | None = None,
        mode: str = "public",
        chunk_size: int = 1024 * 1024,
    ) -> dict[str, Any]:
        """Upload a local file to Media Library via services endpoints (streamed PUT)."""
        lid = location_id or self._location_id
        file_path = Path(path)
        if not file_path.is_file():
            raise FileNotFoundError(str(file_path))

        name = (filename or file_path.name or "").strip() or "upload.bin"
        ct = (content_type or "").strip()
        if not ct:
            guessed, _ = mimetypes.guess_type(name)
            ct = guessed or "application/octet-stream"

        parent_id = (folder_id or "").strip()
        size = int(file_path.stat().st_size)

        created = await self._services_post_json(
            "/medias/files/",
            data={
                "name": name,
                "contentType": ct,
                "parentId": parent_id,
                "altType": "location",
                "altId": lid,
                "size": int(size),
                "mode": mode,
            },
        )
        signed_url = created.get("url")
        file_id = created.get("aknId") or created.get("_id") or created.get("id")
        if not isinstance(signed_url, str) or not signed_url.strip():
            raise RuntimeError(f"Media create did not return signed url (keys={list(created.keys())})")
        if not isinstance(file_id, str) or not file_id.strip():
            raise RuntimeError(f"Media create did not return file id (keys={list(created.keys())})")

        def _iter_chunks() -> Any:
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(max(1, int(chunk_size)))
                    if not chunk:
                        break
                    yield chunk

        async with httpx.AsyncClient(timeout=60.0) as raw:
            put = await raw.put(signed_url, content=_iter_chunks(), headers={"Content-Type": ct})
            put.raise_for_status()

        verified = await self._services_post_json(
            "/medias/files/verify",
            data={
                "altId": lid,
                "altType": "location",
                "id": file_id,
                "mode": mode,
            },
        )
        return verified

    async def list_all_files(
        self,
        *,
        location_id: str | None = None,
        page_size: int = 200,
        # 1000 pages can be huge (time/memory) on large accounts; keep a safe default.
        max_pages: int = 25,
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
