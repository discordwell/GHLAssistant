"""Custom Fields API - Custom field management for GHL locations."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .client import GHLClient


class CustomFieldsAPI:
    """Custom Fields API for GoHighLevel.

    Usage:
        async with GHLClient.from_session() as ghl:
            # List custom fields
            fields = await ghl.custom_fields.list()

            # Get custom field details
            field = await ghl.custom_fields.get("field_id")

            # Create custom field
            field = await ghl.custom_fields.create(
                name="Lead Score",
                field_key="lead_score",
                data_type="NUMBER",
            )

            # Update custom field
            await ghl.custom_fields.update("field_id", name="New Name")

            # Delete custom field
            await ghl.custom_fields.delete("field_id")
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
        """List all custom fields for location.

        Returns:
            {"customFields": [{"id": ..., "name": ..., "fieldKey": ..., "dataType": ...}, ...]}
        """
        lid = location_id or self._location_id
        return await self._client._get(f"/locations/{lid}/customFields")

    async def get(self, field_id: str, location_id: str | None = None) -> dict[str, Any]:
        """Get custom field details.

        Args:
            field_id: The custom field ID
            location_id: Override default location

        Returns:
            {"customField": {...}}
        """
        lid = location_id or self._location_id
        return await self._client._get(f"/locations/{lid}/customFields/{field_id}")

    async def create(
        self,
        name: str,
        field_key: str,
        data_type: str = "TEXT",
        placeholder: str | None = None,
        position: int | None = None,
        location_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new custom field.

        Args:
            name: Display name for the field
            field_key: Unique key for the field (used in API)
            data_type: Field type - TEXT, NUMBER, DATE, CHECKBOX, DROPDOWN, TEXTAREA, etc.
            placeholder: Placeholder text
            position: Display position
            location_id: Override default location

        Returns:
            {"customField": {...}} with created field data
        """
        lid = location_id or self._location_id
        data: dict[str, Any] = {
            "name": name,
            "fieldKey": field_key,
            "dataType": data_type,
        }
        if placeholder:
            data["placeholder"] = placeholder
        if position is not None:
            data["position"] = position

        return await self._client._post(f"/locations/{lid}/customFields", data)

    async def update(
        self,
        field_id: str,
        name: str | None = None,
        placeholder: str | None = None,
        position: int | None = None,
        location_id: str | None = None,
    ) -> dict[str, Any]:
        """Update a custom field.

        Args:
            field_id: The custom field ID to update
            name: New display name
            placeholder: New placeholder text
            position: New display position
            location_id: Override default location

        Returns:
            {"customField": {...}} with updated field data
        """
        lid = location_id or self._location_id
        data: dict[str, Any] = {}
        if name is not None:
            data["name"] = name
        if placeholder is not None:
            data["placeholder"] = placeholder
        if position is not None:
            data["position"] = position

        return await self._client._put(f"/locations/{lid}/customFields/{field_id}", data)

    async def delete(self, field_id: str, location_id: str | None = None) -> dict[str, Any]:
        """Delete a custom field.

        Args:
            field_id: The custom field ID to delete
            location_id: Override default location

        Returns:
            {"succeeded": true} or error
        """
        lid = location_id or self._location_id
        return await self._client._delete(f"/locations/{lid}/customFields/{field_id}")
