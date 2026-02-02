"""Surveys API - Survey operations for GHL."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .client import GHLClient


class SurveysAPI:
    """Surveys API for GoHighLevel.

    Usage:
        async with GHLClient.from_session() as ghl:
            # List surveys
            surveys = await ghl.surveys.list()

            # Get survey details
            survey = await ghl.surveys.get("survey_id")

            # Get survey submissions
            submissions = await ghl.surveys.submissions("survey_id")
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
        """List all surveys for location.

        Returns:
            {"surveys": [{"_id": ..., "name": ..., ...}, ...]}
        """
        lid = location_id or self._location_id
        return await self._client._get("/surveys/", locationId=lid)

    async def get(self, survey_id: str) -> dict[str, Any]:
        """Get survey details including questions and configuration.

        Args:
            survey_id: The survey ID

        Returns:
            {"survey": {...}} with full survey configuration
        """
        return await self._client._get(f"/surveys/{survey_id}")

    async def submissions(
        self,
        survey_id: str,
        limit: int = 50,
        page: int = 1,
        location_id: str | None = None,
    ) -> dict[str, Any]:
        """Get survey submissions.

        Args:
            survey_id: The survey ID
            limit: Max submissions to return (max 100)
            page: Page number
            location_id: Override default location

        Returns:
            {"submissions": [...], "meta": {"total": N, ...}}
        """
        lid = location_id or self._location_id
        return await self._client._get(
            "/surveys/submissions",
            locationId=lid,
            surveyId=survey_id,
            limit=min(limit, 100),
            page=page,
        )

    async def all_submissions(
        self,
        limit: int = 50,
        page: int = 1,
        location_id: str | None = None,
    ) -> dict[str, Any]:
        """Get all survey submissions across all surveys.

        Args:
            limit: Max submissions to return
            page: Page number
            location_id: Override default location

        Returns:
            {"submissions": [...], "meta": {...}}
        """
        lid = location_id or self._location_id
        return await self._client._get(
            "/surveys/submissions",
            locationId=lid,
            limit=min(limit, 100),
            page=page,
        )
