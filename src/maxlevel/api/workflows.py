"""Workflows API - Automation workflow operations for GHL."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .client import GHLClient


class WorkflowsAPI:
    """Workflows API for GoHighLevel.

    Usage:
        async with GHLClient.from_session() as ghl:
            # List workflows
            workflows = await ghl.workflows.list()

            # Get workflow details
            workflow = await ghl.workflows.get("workflow_id")

            # Add contact to workflow
            await ghl.workflows.add_contact("workflow_id", "contact_id")
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
        """List all workflows for location.

        Returns:
            {"workflows": [{"id": ..., "name": ..., "status": "draft"|"published"}, ...]}
        """
        lid = location_id or self._location_id
        return await self._client._get("/workflows/", locationId=lid)

    async def get(self, workflow_id: str) -> dict[str, Any]:
        """Get workflow details.

        Args:
            workflow_id: The workflow ID

        Returns:
            Workflow data including steps/actions
        """
        return await self._client._get(f"/workflows/{workflow_id}")

    async def add_contact(
        self,
        workflow_id: str,
        contact_id: str,
        location_id: str | None = None,
    ) -> dict[str, Any]:
        """Add a contact to a workflow.

        Args:
            workflow_id: The workflow ID
            contact_id: The contact ID to add
            location_id: Override default location

        Returns:
            Result of adding contact
        """
        lid = location_id or self._location_id
        return await self._client._post(
            f"/workflows/{workflow_id}/contacts",
            {"contactId": contact_id, "locationId": lid},
        )

    async def remove_contact(
        self,
        workflow_id: str,
        contact_id: str,
        location_id: str | None = None,
    ) -> dict[str, Any]:
        """Remove a contact from a workflow.

        Args:
            workflow_id: The workflow ID
            contact_id: The contact ID to remove
            location_id: Override default location
        """
        lid = location_id or self._location_id
        return await self._client._delete(
            f"/workflows/{workflow_id}/contacts/{contact_id}?locationId={lid}"
        )
