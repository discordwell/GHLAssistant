"""Tags API - Tag management for GHL locations."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .client import GHLClient


class TagsAPI:
    """Tags API for GoHighLevel.

    Usage:
        async with GHLClient.from_session() as ghl:
            # List tags
            tags = await ghl.tags.list()

            # Get tag details
            tag = await ghl.tags.get("tag_id")

            # Create tag
            tag = await ghl.tags.create("hot-lead")

            # Update tag
            await ghl.tags.update("tag_id", name="warm-lead")

            # Delete tag
            await ghl.tags.delete("tag_id")
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
        """List all tags for location.

        Returns:
            {"tags": [{"_id": ..., "name": ..., ...}, ...]}
        """
        lid = location_id or self._location_id
        return await self._client._get("/tags/", locationId=lid)

    async def get(self, tag_id: str) -> dict[str, Any]:
        """Get tag details.

        Args:
            tag_id: The tag ID

        Returns:
            {"tag": {...}}
        """
        return await self._client._get(f"/tags/{tag_id}")

    async def create(
        self,
        name: str,
        location_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new tag.

        Args:
            name: Tag name
            location_id: Override default location

        Returns:
            {"tag": {...}} with created tag data
        """
        lid = location_id or self._location_id
        return await self._client._post("/tags/", {"name": name, "locationId": lid})

    async def update(
        self,
        tag_id: str,
        name: str,
    ) -> dict[str, Any]:
        """Update a tag.

        Args:
            tag_id: The tag ID to update
            name: New tag name

        Returns:
            {"tag": {...}} with updated tag data
        """
        return await self._client._put(f"/tags/{tag_id}", {"name": name})

    async def delete(self, tag_id: str) -> dict[str, Any]:
        """Delete a tag.

        Args:
            tag_id: The tag ID to delete

        Returns:
            {"succeeded": true} or error
        """
        return await self._client._delete(f"/tags/{tag_id}")
