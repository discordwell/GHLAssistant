"""Tests for GHL Surveys routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from crm.models.location import Location


@pytest.mark.asyncio
async def test_surveys_page_no_ghl_location(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/surveys/")
    assert response.status_code == 200
    assert "GHL" in response.text or "No GHL" in response.text


@pytest.mark.asyncio
async def test_surveys_page_ghl_linked(client: AsyncClient, location: Location, db):
    location.ghl_location_id = "ghl_loc_123"
    await db.commit()

    mock_data = {"surveys": [{"_id": "s1", "name": "Feedback Survey"}]}
    with patch("crm.routers.ghl_surveys.fetch_surveys", new_callable=AsyncMock, return_value=mock_data):
        response = await client.get(f"/loc/{location.slug}/surveys/")
    assert response.status_code == 200
    assert "Feedback Survey" in response.text


@pytest.mark.asyncio
async def test_surveys_page_ghl_not_linked_error(client: AsyncClient, location: Location, db):
    location.ghl_location_id = "ghl_loc_123"
    await db.commit()

    from crm.services.ghl_svc import GHLNotLinkedError
    with patch("crm.routers.ghl_surveys.fetch_surveys", new_callable=AsyncMock, side_effect=GHLNotLinkedError("No token")):
        response = await client.get(f"/loc/{location.slug}/surveys/")
    assert response.status_code == 200
    assert "GHL" in response.text


@pytest.mark.asyncio
async def test_surveys_page_api_error(client: AsyncClient, location: Location, db):
    location.ghl_location_id = "ghl_loc_123"
    await db.commit()

    with patch("crm.routers.ghl_surveys.fetch_surveys", new_callable=AsyncMock, side_effect=Exception("timeout")):
        response = await client.get(f"/loc/{location.slug}/surveys/")
    assert response.status_code == 200
    assert "Failed" in response.text


@pytest.mark.asyncio
async def test_survey_submissions(client: AsyncClient, location: Location, db):
    location.ghl_location_id = "ghl_loc_123"
    await db.commit()

    mock_data = {"submissions": [{"contactId": "c1", "createdAt": "2025-01-01T00:00:00Z"}], "meta": {"total": 1}}
    with patch("crm.routers.ghl_surveys.fetch_survey_submissions", new_callable=AsyncMock, return_value=mock_data):
        response = await client.get(f"/loc/{location.slug}/surveys/s1/submissions")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_survey_submissions_no_ghl(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/surveys/s1/submissions")
    assert response.status_code == 200
