"""Opportunities API - Pipeline and opportunity operations for GHL."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from .client import GHLClient


class OpportunitiesAPI:
    """Opportunities/Pipelines API for GoHighLevel.

    Usage:
        async with GHLClient.from_session() as ghl:
            # List pipelines
            pipelines = await ghl.opportunities.pipelines()

            # Create opportunity
            opp = await ghl.opportunities.create(
                pipeline_id="...",
                stage_id="...",
                contact_id="...",
                name="New Deal",
                value=5000,
            )

            # Move to new stage
            await ghl.opportunities.move_stage("opp_id", "new_stage_id")
    """

    def __init__(self, client: "GHLClient"):
        self._client = client

    @property
    def _location_id(self) -> str:
        lid = self._client.config.location_id
        if not lid:
            raise ValueError("location_id required")
        return lid

    async def pipelines(self, location_id: str | None = None) -> dict[str, Any]:
        """List all pipelines for location.

        Returns:
            {"pipelines": [{"id": ..., "name": ..., "stages": [...]}, ...]}
        """
        lid = location_id or self._location_id
        return await self._client._get("/opportunities/pipelines", locationId=lid)

    async def list_all(
        self,
        *,
        location_id: str | None = None,
        page_size: int = 200,
        max_pages: int = 25,
    ) -> list[dict]:
        """List opportunities for a location (best-effort).

        Uses the newer POST `/opportunities/search` endpoint.
        Some filter fields are strict/undocumented; we fetch pages and
        filter client-side in `list()`.
        """
        lid = location_id or self._location_id
        page_size = max(1, int(page_size))
        max_pages = max(1, int(max_pages))

        all_items: list[dict] = []
        seen_ids: set[str] = set()
        skip = 0
        allow_skip = True

        for _ in range(max_pages):
            payload: dict[str, Any] = {"locationId": lid, "limit": page_size}
            if skip and allow_skip:
                payload["skip"] = skip

            try:
                resp = await self._client._post("/opportunities/search", payload)
            except httpx.HTTPStatusError as exc:
                # Some deployments may not accept `skip`; retry once without it.
                body = ""
                try:
                    body = exc.response.text or ""
                except Exception:
                    body = ""
                if exc.response.status_code == 422 and "property skip should not exist" in body:
                    allow_skip = False
                    payload.pop("skip", None)
                    resp = await self._client._post("/opportunities/search", payload)
                else:
                    raise

            items = resp.get("opportunities", [])
            if not isinstance(items, list) or not items:
                break

            new_count = 0
            for item in items:
                if not isinstance(item, dict):
                    continue
                oid = item.get("id", item.get("_id", ""))
                if isinstance(oid, str) and oid:
                    if oid in seen_ids:
                        continue
                    seen_ids.add(oid)
                all_items.append(item)
                new_count += 1

            if new_count == 0:
                break

            total = resp.get("total")
            if isinstance(total, int) and total >= 0 and len(all_items) >= total:
                break

            if not allow_skip:
                break
            skip += len(items)

        return all_items

    async def list(
        self,
        pipeline_id: str | None = None,
        stage_id: str | None = None,
        contact_id: str | None = None,
        limit: int = 20,
        location_id: str | None = None,
    ) -> dict[str, Any]:
        """List opportunities.

        Args:
            pipeline_id: Filter by pipeline
            stage_id: Filter by stage
            contact_id: Filter by contact
            limit: Max results
            location_id: Override default location

        Returns:
            {"opportunities": [...], "meta": {...}}
        """
        items = await self.list_all(location_id=location_id)

        def _match(item: dict) -> bool:
            if pipeline_id:
                pid = item.get("pipelineId", item.get("pipeline_id"))
                if pid != pipeline_id:
                    return False
            if stage_id:
                sid = item.get("pipelineStageId", item.get("pipeline_stage_id"))
                if sid != stage_id:
                    return False
            if contact_id:
                cid = item.get("contactId", item.get("contact_id"))
                if cid != contact_id:
                    return False
            return True

        filtered = [i for i in items if isinstance(i, dict) and _match(i)]
        lim = max(0, int(limit))
        return {"opportunities": filtered[:lim] if lim else filtered, "total": len(filtered)}

    async def get(self, opportunity_id: str) -> dict[str, Any]:
        """Get opportunity details.

        Args:
            opportunity_id: The opportunity ID

        Returns:
            {"opportunity": {...}}
        """
        return await self._client._get(f"/opportunities/{opportunity_id}")

    async def create(
        self,
        pipeline_id: str,
        stage_id: str,
        contact_id: str,
        name: str,
        value: float | None = None,
        status: str = "open",
        location_id: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Create a new opportunity.

        Args:
            pipeline_id: The pipeline ID
            stage_id: The initial stage ID
            contact_id: Associated contact ID
            name: Opportunity name/title
            value: Monetary value
            status: Status ("open", "won", "lost", "abandoned")
            location_id: Override default location
            **kwargs: Additional fields

        Returns:
            {"opportunity": {...}}
        """
        lid = location_id or self._location_id
        data = {
            "locationId": lid,
            "pipelineId": pipeline_id,
            "pipelineStageId": stage_id,
            "contactId": contact_id,
            "name": name,
            "status": status,
        }
        if value is not None:
            data["monetaryValue"] = value
        data.update(kwargs)

        return await self._client._post("/opportunities/", data)

    async def update(
        self,
        opportunity_id: str,
        name: str | None = None,
        value: float | None = None,
        status: str | None = None,
        stage_id: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Update an opportunity.

        Args:
            opportunity_id: The opportunity ID
            name: New name
            value: New value
            status: New status
            stage_id: Move to new stage
            **kwargs: Additional fields

        Returns:
            {"opportunity": {...}}
        """
        data = {}
        if name is not None:
            data["name"] = name
        if value is not None:
            data["monetaryValue"] = value
        if status is not None:
            data["status"] = status
        if stage_id is not None:
            data["pipelineStageId"] = stage_id
        data.update(kwargs)

        return await self._client._put(f"/opportunities/{opportunity_id}", data)

    async def delete(self, opportunity_id: str) -> dict[str, Any]:
        """Delete an opportunity.

        Args:
            opportunity_id: The opportunity ID

        Returns:
            Deletion result
        """
        return await self._client._delete(f"/opportunities/{opportunity_id}")

    async def move_stage(self, opportunity_id: str, stage_id: str) -> dict[str, Any]:
        """Move opportunity to a new stage.

        Args:
            opportunity_id: The opportunity ID
            stage_id: The target stage ID

        Returns:
            Updated opportunity
        """
        return await self.update(opportunity_id, stage_id=stage_id)

    async def mark_won(self, opportunity_id: str) -> dict[str, Any]:
        """Mark opportunity as won."""
        return await self.update(opportunity_id, status="won")

    async def mark_lost(self, opportunity_id: str) -> dict[str, Any]:
        """Mark opportunity as lost."""
        return await self.update(opportunity_id, status="lost")
