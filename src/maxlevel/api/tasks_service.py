"""Services-domain Tasks API.

The v2 UI queries Tasks via a custom-object record search:
  POST https://services.leadconnectorhq.com/objects/task/records/search

Auth is via the Firebase `token-id` header captured from browser traffic.
"""

from __future__ import annotations

import os
from typing import Any, TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from .client import GHLClient


SERVICES_BASE_URL = "https://services.leadconnectorhq.com"
TASK_CONTACT_ASSOCIATION = "TASK_CONTACT_ASSOCIATION"


class TasksServiceAPI:
    """Tasks API using services.leadconnectorhq.com endpoints."""

    def __init__(self, client: "GHLClient"):
        self._client = client

    def _services_base_url(self) -> str:
        override = os.environ.get("MAXLEVEL_SERVICES_BASE_URL")
        if isinstance(override, str) and override.strip().lower().startswith(("http://", "https://")):
            return override.strip().rstrip("/")
        return SERVICES_BASE_URL

    def _services_headers(self) -> dict[str, str]:
        token_id = self._client.config.token_id
        if not isinstance(token_id, str) or not token_id.strip():
            raise RuntimeError(
                "token_id missing (required for services.* Tasks endpoints). "
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

    async def _post_json(self, path: str, *, data: dict[str, Any]) -> dict[str, Any]:
        client = self._require_http_client()
        url = f"{self._services_base_url()}{path}"
        headers = dict(self._services_headers())
        headers["Content-Type"] = "application/json"
        resp = await client.post(url, json=data, headers=headers)
        resp.raise_for_status()
        return resp.json()

    async def search(
        self,
        *,
        location_id: str,
        filters: list[dict[str, Any]],
        page: int = 1,
        page_limit: int = 20,
        sort: list[dict[str, Any]] | None = None,
        query: str = "",
        include_recurring_task_configs: bool = True,
        ignore_assigned_to_permission: bool = True,
    ) -> dict[str, Any]:
        """Raw task record search.

        Mirrors UI call:
          POST /objects/task/records/search
        """
        if not isinstance(location_id, str) or not location_id.strip():
            raise ValueError("location_id required")
        payload: dict[str, Any] = {
            "filters": filters,
            "locationId": location_id,
            "sort": sort or [{"field": "properties.dueDate", "direction": "desc"}],
            "pageLimit": int(page_limit),
            "includeRecurringTaskConfigs": bool(include_recurring_task_configs),
            "ignoreAssignedToPermission": bool(ignore_assigned_to_permission),
            "page": int(page),
            "query": query or "",
        }
        return await self._post_json("/objects/task/records/search", data=payload)

    async def list_by_contact(
        self,
        contact_id: str,
        *,
        location_id: str,
        page_limit: int = 50,
        max_pages: int = 100,
        sort_field: str = "properties.dueDate",
        sort_direction: str = "desc",
        query: str = "",
        include_recurring_task_configs: bool = True,
        ignore_assigned_to_permission: bool = True,
    ) -> dict[str, Any]:
        """List all tasks for a contact (best-effort pagination)."""
        if not isinstance(contact_id, str) or not contact_id.strip():
            raise ValueError("contact_id required")
        page_limit = max(1, min(int(page_limit), 200))
        max_pages = max(1, int(max_pages))

        filters = [
            {
                "group": "OR",
                "filters": [
                    {
                        "field": f"relations.{TASK_CONTACT_ASSOCIATION}",
                        "operator": "eq",
                        "value": [contact_id],
                    }
                ],
            }
        ]
        sort = [{"field": sort_field, "direction": sort_direction}]

        records: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for page in range(1, max_pages + 1):
            resp = await self.search(
                location_id=location_id,
                filters=filters,
                page=page,
                page_limit=page_limit,
                sort=sort,
                query=query,
                include_recurring_task_configs=include_recurring_task_configs,
                ignore_assigned_to_permission=ignore_assigned_to_permission,
            )
            batch = resp.get("customObjectRecords")
            if not isinstance(batch, list) or not batch:
                break

            added = 0
            for item in batch:
                if not isinstance(item, dict):
                    continue
                rid = item.get("id") or item.get("_id") or ""
                if isinstance(rid, str) and rid:
                    if rid in seen_ids:
                        continue
                    seen_ids.add(rid)
                records.append(item)
                added += 1

            if added == 0:
                break

            total = resp.get("total")
            if isinstance(total, int) and len(records) >= total:
                break

            if len(batch) < page_limit:
                break

        return {"tasks": records}

