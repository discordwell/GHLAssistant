"""Custom Values API - Custom value management for GHL locations."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .client import GHLClient


class CustomValuesAPI:
    """Custom Values API for GoHighLevel.

    Custom values are location-specific variables that can be used in templates,
    emails, SMS, etc. (e.g., {{location.business_name}}, {{location.address}}).

    Usage:
        async with GHLClient.from_session() as ghl:
            # List custom values
            values = await ghl.custom_values.list()

            # Get custom value details
            value = await ghl.custom_values.get("value_id")

            # Create custom value
            value = await ghl.custom_values.create(
                name="Business Hours",
                value="Mon-Fri 9am-5pm",
            )

            # Update custom value
            await ghl.custom_values.update("value_id", value="Mon-Fri 8am-6pm")

            # Delete custom value
            await ghl.custom_values.delete("value_id")
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
        """List all custom values for location.

        Returns:
            {"customValues": [{"id": ..., "name": ..., "value": ...}, ...]}
        """
        lid = location_id or self._location_id
        return await self._client._get(f"/locations/{lid}/customValues")

    async def get(self, value_id: str, location_id: str | None = None) -> dict[str, Any]:
        """Get custom value details.

        Args:
            value_id: The custom value ID
            location_id: Override default location

        Returns:
            {"customValue": {...}}
        """
        lid = location_id or self._location_id
        return await self._client._get(f"/locations/{lid}/customValues/{value_id}")

    async def create(
        self,
        name: str,
        value: str,
        location_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new custom value.

        Args:
            name: Name/key for the custom value
            value: The value content
            location_id: Override default location

        Returns:
            {"customValue": {...}} with created value data
        """
        lid = location_id or self._location_id
        return await self._client._post(
            f"/locations/{lid}/customValues",
            {"name": name, "value": value},
        )

    async def update(
        self,
        value_id: str,
        name: str | None = None,
        value: str | None = None,
        location_id: str | None = None,
    ) -> dict[str, Any]:
        """Update a custom value.

        Args:
            value_id: The custom value ID to update
            name: New name
            value: New value content
            location_id: Override default location

        Returns:
            {"customValue": {...}} with updated value data
        """
        lid = location_id or self._location_id
        data: dict[str, Any] = {}
        if name is not None:
            data["name"] = name
        if value is not None:
            data["value"] = value

        return await self._client._put(f"/locations/{lid}/customValues/{value_id}", data)

    async def delete(self, value_id: str, location_id: str | None = None) -> dict[str, Any]:
        """Delete a custom value.

        Args:
            value_id: The custom value ID to delete
            location_id: Override default location

        Returns:
            {"succeeded": true} or error
        """
        lid = location_id or self._location_id
        return await self._client._delete(f"/locations/{lid}/customValues/{value_id}")
