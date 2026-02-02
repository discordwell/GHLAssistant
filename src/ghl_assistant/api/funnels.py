"""Funnels API - Funnel and page operations for GHL."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .client import GHLClient


class FunnelsAPI:
    """Funnels API for GoHighLevel.

    Usage:
        async with GHLClient.from_session() as ghl:
            # List funnels
            funnels = await ghl.funnels.list()

            # Get funnel details
            funnel = await ghl.funnels.get("funnel_id")

            # Get funnel pages
            pages = await ghl.funnels.pages("funnel_id")
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
        """List all funnels for location.

        Returns:
            {"funnels": [{"_id": ..., "name": ..., "steps": [...], ...}, ...]}
        """
        lid = location_id or self._location_id
        return await self._client._get("/funnels/", locationId=lid)

    async def get(self, funnel_id: str) -> dict[str, Any]:
        """Get funnel details.

        Args:
            funnel_id: The funnel ID

        Returns:
            {"funnel": {...}} with full funnel configuration
        """
        return await self._client._get(f"/funnels/{funnel_id}")

    async def pages(
        self,
        funnel_id: str,
        limit: int = 50,
        offset: int = 0,
        location_id: str | None = None,
    ) -> dict[str, Any]:
        """Get pages within a funnel.

        Args:
            funnel_id: The funnel ID
            limit: Max pages to return
            offset: Pagination offset
            location_id: Override default location

        Returns:
            {"pages": [{"_id": ..., "name": ..., "path": ..., ...}, ...]}
        """
        lid = location_id or self._location_id
        return await self._client._get(
            f"/funnels/{funnel_id}/pages",
            locationId=lid,
            limit=limit,
            offset=offset,
        )

    async def get_page(self, funnel_id: str, page_id: str) -> dict[str, Any]:
        """Get a specific page within a funnel.

        Args:
            funnel_id: The funnel ID
            page_id: The page ID

        Returns:
            {"page": {...}} with full page configuration
        """
        return await self._client._get(f"/funnels/{funnel_id}/pages/{page_id}")
