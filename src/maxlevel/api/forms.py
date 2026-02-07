"""Forms API - Form operations for GHL."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .client import GHLClient


class FormsAPI:
    """Forms API for GoHighLevel.

    Usage:
        async with GHLClient.from_session() as ghl:
            # List forms
            forms = await ghl.forms.list()

            # Get form details
            form = await ghl.forms.get("form_id")

            # Get form submissions
            submissions = await ghl.forms.submissions("form_id")
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
        """List all forms for location.

        Returns:
            {"forms": [{"_id": ..., "name": ..., ...}, ...], "total": N}
        """
        lid = location_id or self._location_id
        return await self._client._get("/forms/", locationId=lid)

    async def get(self, form_id: str) -> dict[str, Any]:
        """Get form details including fields and styling.

        Args:
            form_id: The form ID

        Returns:
            {"form": {...}} with full form configuration
        """
        return await self._client._get(f"/forms/{form_id}")

    async def submissions(
        self,
        form_id: str,
        limit: int = 50,
        page: int = 1,
        location_id: str | None = None,
    ) -> dict[str, Any]:
        """Get form submissions.

        Args:
            form_id: The form ID
            limit: Max submissions to return (max 100)
            page: Page number
            location_id: Override default location

        Returns:
            {"submissions": [...], "meta": {"total": N, ...}}
        """
        lid = location_id or self._location_id
        return await self._client._get(
            "/forms/submissions",
            locationId=lid,
            formId=form_id,
            limit=min(limit, 100),
            page=page,
        )

    async def all_submissions(
        self,
        limit: int = 50,
        page: int = 1,
        location_id: str | None = None,
    ) -> dict[str, Any]:
        """Get all form submissions across all forms.

        Args:
            limit: Max submissions to return
            page: Page number
            location_id: Override default location

        Returns:
            {"submissions": [...], "meta": {...}}
        """
        lid = location_id or self._location_id
        return await self._client._get(
            "/forms/submissions",
            locationId=lid,
            limit=min(limit, 100),
            page=page,
        )
