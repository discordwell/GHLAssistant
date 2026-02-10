"""Services-domain Notes API.

The v2 UI uses services.leadconnectorhq.com for Notes, backed by a Firebase
ID token in the `token-id` header (not the backend Bearer token).

Endpoints (inferred from UI network traffic):
  POST   /notes/search          — list / search notes
  POST   /notes                 — create a note
  PUT    /notes/{noteId}        — update a note
  DELETE /notes/{noteId}        — delete a note
"""

from __future__ import annotations

import os
from typing import Any, TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from .client import GHLClient


SERVICES_BASE_URL = "https://services.leadconnectorhq.com"


class NotesServiceAPI:
    """Notes API using services.leadconnectorhq.com endpoints."""

    def __init__(self, client: "GHLClient"):
        self._client = client

    # ------------------------------------------------------------------
    # Internal HTTP plumbing
    # ------------------------------------------------------------------

    def _services_base_url(self) -> str:
        override = os.environ.get("MAXLEVEL_SERVICES_BASE_URL")
        if isinstance(override, str) and override.strip().lower().startswith(("http://", "https://")):
            return override.strip().rstrip("/")
        return SERVICES_BASE_URL

    def _services_headers(self) -> dict[str, str]:
        token_id = self._client.config.token_id
        if not isinstance(token_id, str) or not token_id.strip():
            raise RuntimeError(
                "token_id missing (required for services.* Notes endpoints). "
                "Capture a browser session and ensure token-id is discoverable."
            )
        return {
            "token-id": token_id.strip(),
            "Accept": "application/json, text/plain, */*",
            **self._client.REQUIRED_HEADERS,
        }

    def _require_http_client(self) -> httpx.AsyncClient:
        if not getattr(self._client, "_client", None):
            raise RuntimeError("Client not initialized. Use 'async with' context.")
        return self._client._client  # type: ignore[return-value]

    def _json_headers(self) -> dict[str, str]:
        headers = dict(self._services_headers())
        headers["Content-Type"] = "application/json"
        return headers

    async def _post_json(
        self, path: str, *, data: dict[str, Any], params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        client = self._require_http_client()
        url = f"{self._services_base_url()}{path}"
        resp = await client.post(url, json=data, headers=self._json_headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    async def _put_json(
        self, path: str, *, data: dict[str, Any], params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        client = self._require_http_client()
        url = f"{self._services_base_url()}{path}"
        resp = await client.put(url, json=data, headers=self._json_headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    async def _delete(self, path: str, *, params: dict[str, str] | None = None) -> dict[str, Any]:
        client = self._require_http_client()
        url = f"{self._services_base_url()}{path}"
        resp = await client.delete(url, headers=self._services_headers(), params=params)
        resp.raise_for_status()
        if resp.content:
            return resp.json()
        return {"success": True}

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def search(
        self,
        *,
        location_id: str,
        relations: list[dict[str, Any]],
        limit: int = 10,
        skip: int = 0,
        include_relation_records: bool = True,
        sort_by: str = "dateAdded",
        sort_order: str = "desc",
    ) -> dict[str, Any]:
        """Raw notes search.

        Mirrors UI call:
          POST /notes/search
        """
        if not isinstance(location_id, str) or not location_id.strip():
            raise ValueError("location_id required")
        payload: dict[str, Any] = {
            "relations": relations,
            "limit": int(limit),
            "skip": int(skip),
            "locationId": location_id,
            "includeRelationRecords": bool(include_relation_records),
            "sortBy": sort_by,
            "sortOrder": sort_order,
        }
        return await self._post_json("/notes/search", data=payload)

    async def list_by_contact(
        self,
        contact_id: str,
        *,
        location_id: str,
        page_size: int = 100,
        max_pages: int = 100,
        include_relation_records: bool = True,
        sort_by: str = "dateAdded",
        sort_order: str = "desc",
    ) -> dict[str, Any]:
        """List all notes for a contact (best-effort pagination)."""
        if not isinstance(contact_id, str) or not contact_id.strip():
            raise ValueError("contact_id required")
        page_size = max(1, min(int(page_size), 500))
        max_pages = max(1, int(max_pages))

        notes: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        skip = 0
        for _ in range(max_pages):
            resp = await self.search(
                location_id=location_id,
                relations=[{"objectKey": "contact", "recordId": contact_id}],
                limit=page_size,
                skip=skip,
                include_relation_records=include_relation_records,
                sort_by=sort_by,
                sort_order=sort_order,
            )
            batch = resp.get("notes")
            if not isinstance(batch, list) or not batch:
                break

            added = 0
            for item in batch:
                if not isinstance(item, dict):
                    continue
                nid = item.get("id") or item.get("_id") or ""
                if isinstance(nid, str) and nid:
                    if nid in seen_ids:
                        continue
                    seen_ids.add(nid)
                notes.append(item)
                added += 1

            # Defensive guard when pagination yields no new items.
            if added == 0:
                break

            if len(batch) < page_size:
                break
            skip += len(batch)

        return {"notes": notes}

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    async def create(
        self,
        *,
        location_id: str,
        body: str,
        contact_id: str | None = None,
        relations: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Create a new note.

        Uses ``POST /notes/?locationId=…`` (services domain).
        ``locationId`` is sent as a **query parameter** — the services
        endpoint rejects it in the JSON body.

        Args:
            location_id: GHL location ID.
            body: Note body (HTML is accepted).
            contact_id: Shorthand — automatically builds a contact relation.
            relations: Explicit relations list. Overrides *contact_id* if given.

        Returns:
            ``{"note": {id, body, …}}`` — the created note object.
        """
        if not isinstance(location_id, str) or not location_id.strip():
            raise ValueError("location_id required")
        if not isinstance(body, str) or not body.strip():
            raise ValueError("body required")

        if relations is None:
            if not isinstance(contact_id, str) or not contact_id.strip():
                raise ValueError("Either contact_id or relations is required")
            relations = [{"objectKey": "contact", "recordId": contact_id}]

        payload: dict[str, Any] = {
            "body": body,
            "relations": relations,
        }
        return await self._post_json(
            "/notes/", data=payload, params={"locationId": location_id},
        )

    async def update(
        self,
        note_id: str,
        *,
        location_id: str,
        body: str | None = None,
        relations: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Update an existing note.

        Uses ``PUT /notes/{noteId}?locationId=…``.

        Args:
            note_id: ID of the note to update.
            location_id: GHL location ID (required as query param).
            body: New note body (HTML is accepted).
            relations: Updated relations (optional).

        Returns:
            Updated note object from the API.
        """
        if not isinstance(note_id, str) or not note_id.strip():
            raise ValueError("note_id required")
        if not isinstance(location_id, str) or not location_id.strip():
            raise ValueError("location_id required")

        payload: dict[str, Any] = {}
        if body is not None:
            payload["body"] = body
        if relations is not None:
            payload["relations"] = relations

        if not payload:
            raise ValueError("At least one field to update is required")

        return await self._put_json(
            f"/notes/{note_id}", data=payload, params={"locationId": location_id},
        )

    async def delete(
        self,
        note_id: str,
        *,
        location_id: str,
    ) -> dict[str, Any]:
        """Delete a note.

        Uses ``DELETE /notes/{noteId}?locationId=…``.

        Args:
            note_id: ID of the note to delete.
            location_id: GHL location ID (required as query param).

        Returns:
            API response (usually ``{"success": True}``).
        """
        if not isinstance(note_id, str) or not note_id.strip():
            raise ValueError("note_id required")
        if not isinstance(location_id, str) or not location_id.strip():
            raise ValueError("location_id required")
        return await self._delete(
            f"/notes/{note_id}", params={"locationId": location_id},
        )

