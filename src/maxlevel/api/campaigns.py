"""Campaigns API - Email/SMS campaign operations for GHL."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .client import GHLClient


class CampaignsAPI:
    """Campaigns API for GoHighLevel.

    Usage:
        async with GHLClient.from_session() as ghl:
            # List campaigns
            campaigns = await ghl.campaigns.list()

            # Get campaign details
            campaign = await ghl.campaigns.get("campaign_id")
    """

    def __init__(self, client: "GHLClient"):
        self._client = client

    @property
    def _location_id(self) -> str:
        lid = self._client.config.location_id
        if not lid:
            raise ValueError("location_id required")
        return lid

    async def list(self, location_id: str | None = None) -> dict[str, Any]:
        """List all campaigns for location.

        Returns:
            {"campaigns": [{"id": ..., "name": ..., "status": ...}, ...]}
        """
        lid = location_id or self._location_id
        return await self._client._get("/campaigns/", locationId=lid)

    async def get(self, campaign_id: str) -> dict[str, Any]:
        """Get campaign details.

        Args:
            campaign_id: The campaign ID

        Returns:
            {"campaign": {...}} with full campaign configuration
        """
        return await self._client._get(f"/campaigns/{campaign_id}")
