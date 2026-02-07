"""Opportunities API - Pipeline and opportunity operations for GHL."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

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
        lid = location_id or self._location_id
        params = {"locationId": lid, "limit": limit}
        if pipeline_id:
            params["pipelineId"] = pipeline_id
        if stage_id:
            params["stageId"] = stage_id
        if contact_id:
            params["contactId"] = contact_id

        return await self._client._get("/opportunities/", **params)

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
