"""Services-domain Tasks API.

The v2 UI queries Tasks via a custom-object record search:
  POST   /objects/task/records/search          — list / search tasks
  POST   /objects/task/records                 — create a task record
  PUT    /objects/task/records/{taskId}         — update a task record
  DELETE /objects/task/records/{taskId}         — delete a task record

Tasks are stored as custom-object records keyed by ``"task"`` and linked to
contacts via the ``TASK_CONTACT_ASSOCIATION`` relation.

Auth is via the Firebase ``token-id`` header captured from browser traffic.
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

    def _json_headers(self) -> dict[str, str]:
        headers = dict(self._services_headers())
        headers["Content-Type"] = "application/json"
        return headers

    async def _post_json(self, path: str, *, data: dict[str, Any]) -> dict[str, Any]:
        client = self._require_http_client()
        url = f"{self._services_base_url()}{path}"
        resp = await client.post(url, json=data, headers=self._json_headers())
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

    async def _delete(
        self,
        path: str,
        *,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
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

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    async def create(
        self,
        *,
        location_id: str,
        title: str,
        contact_id: str | None = None,
        due_date: str | None = None,
        description: str | None = None,
        status: str = "incomplete",
        assigned_to: str | None = None,
        relations: list[dict[str, str]] | None = None,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a new task record.

        Uses ``POST /objects/task/records``.

        **Relation format** (validated by the API)::

            [{"associationId": "TASK_CONTACT_ASSOCIATION", "recordId": "<contactId>"}]

        When *contact_id* is provided the relation is built automatically.

        Note: ``dueDate`` is **required** when *relations* are present.

        Args:
            location_id: GHL location ID.
            title: Task title.
            contact_id: Shorthand — automatically builds a contact relation.
            due_date: ISO-8601 due date (e.g. ``"2026-02-15T00:00:00.000Z"``).
                Required when linking to a contact.
            description: Task description / body text.
            status: ``"incomplete"`` (default) or ``"completed"``.
            assigned_to: User ID to assign the task to.
            relations: Explicit relations list of
                ``{"associationId": …, "recordId": …}`` dicts.
                Overrides *contact_id* if given.
            properties: Raw properties dict — merged with any explicit
                field arguments above.

        Returns:
            ``{"record": {id, objectKey, properties, …}}`` — the created record.
        """
        if not isinstance(location_id, str) or not location_id.strip():
            raise ValueError("location_id required")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("title required")

        props: dict[str, Any] = dict(properties or {})
        props["title"] = title
        if due_date is not None:
            props["dueDate"] = due_date
        if description is not None:
            props["description"] = description
        if status:
            props["status"] = status
        if assigned_to is not None:
            props["assignedTo"] = assigned_to

        if relations is None and contact_id:
            if "dueDate" not in props:
                raise ValueError(
                    "due_date is required when linking a task to a contact"
                )
            relations = [
                {"associationId": TASK_CONTACT_ASSOCIATION, "recordId": contact_id}
            ]

        payload: dict[str, Any] = {
            "locationId": location_id,
            "properties": props,
        }
        if relations:
            payload["relations"] = relations

        return await self._post_json("/objects/task/records", data=payload)

    async def update(
        self,
        task_id: str,
        *,
        location_id: str,
        title: str | None = None,
        due_date: str | None = None,
        description: str | None = None,
        status: str | None = None,
        assigned_to: str | None = None,
        relations: list[dict[str, str]] | None = None,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Update an existing task record.

        Uses ``PUT /objects/task/records/{taskId}?locationId=…``.
        ``locationId`` **must** be a query parameter.

        Only provided fields are sent; ``None`` values are omitted.

        Args:
            task_id: ID of the task record.
            location_id: GHL location ID (required as query param).
            title: New title.
            due_date: New due date (ISO-8601).
            description: New description.
            status: ``"incomplete"`` or ``"completed"``.
            assigned_to: User ID to reassign.
            relations: Updated relations list.
            properties: Raw properties dict — merged with field args.

        Returns:
            ``{"record": {…}}`` — the updated record.
        """
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task_id required")
        if not isinstance(location_id, str) or not location_id.strip():
            raise ValueError("location_id required")

        props: dict[str, Any] = dict(properties or {})
        if title is not None:
            props["title"] = title
        if due_date is not None:
            props["dueDate"] = due_date
        if description is not None:
            props["description"] = description
        if status is not None:
            props["status"] = status
        if assigned_to is not None:
            props["assignedTo"] = assigned_to

        payload: dict[str, Any] = {}
        if props:
            payload["properties"] = props
        if relations is not None:
            payload["relations"] = relations

        if not payload:
            raise ValueError("At least one field to update is required")

        return await self._put_json(
            f"/objects/task/records/{task_id}",
            data=payload,
            params={"locationId": location_id},
        )

    async def toggle_status(
        self,
        task_id: str,
        *,
        location_id: str,
        completed: bool,
    ) -> dict[str, Any]:
        """Toggle a task between completed and incomplete.

        Convenience wrapper around :meth:`update`.

        Args:
            task_id: ID of the task record.
            location_id: GHL location ID.
            completed: ``True`` to mark done, ``False`` to re-open.

        Returns:
            Updated task record from the API.
        """
        return await self.update(
            task_id,
            location_id=location_id,
            status="completed" if completed else "incomplete",
        )

    async def delete(
        self,
        task_id: str,
        *,
        location_id: str | None = None,
    ) -> dict[str, Any]:
        """Delete a task record.

        Uses ``DELETE /objects/task/records/{taskId}``.

        Args:
            task_id: ID of the task record.

        Returns:
            ``{"id": …, "success": true}``
        """
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task_id required")
        params: dict[str, str] | None = None
        if isinstance(location_id, str) and location_id.strip():
            # Some services-domain write endpoints require locationId in the query
            # string; delete *may* accept it. Include when known for robustness.
            params = {"locationId": location_id.strip()}
        return await self._delete(f"/objects/task/records/{task_id}", params=params)
