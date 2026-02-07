"""Tests for GHL Campaigns routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from crm.models.location import Location


@pytest.mark.asyncio
async def test_campaigns_page_no_ghl_location(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/campaigns/")
    assert response.status_code == 200
    assert "GHL" in response.text or "No GHL" in response.text


@pytest.mark.asyncio
async def test_campaigns_page_ghl_linked(client: AsyncClient, location: Location, db):
    location.ghl_location_id = "ghl_loc_123"
    await db.commit()

    mock_data = {"campaigns": [{"id": "c1", "name": "Welcome Series", "status": "published"}]}
    with patch("crm.routers.ghl_campaigns.fetch_campaigns", new_callable=AsyncMock, return_value=mock_data):
        response = await client.get(f"/loc/{location.slug}/campaigns/")
    assert response.status_code == 200
    assert "Welcome Series" in response.text


@pytest.mark.asyncio
async def test_campaigns_page_api_error(client: AsyncClient, location: Location, db):
    location.ghl_location_id = "ghl_loc_123"
    await db.commit()

    with patch("crm.routers.ghl_campaigns.fetch_campaigns", new_callable=AsyncMock, side_effect=Exception("err")):
        response = await client.get(f"/loc/{location.slug}/campaigns/")
    assert response.status_code == 200
    assert "Failed" in response.text


@pytest.mark.asyncio
async def test_campaign_detail(client: AsyncClient, location: Location, db):
    location.ghl_location_id = "ghl_loc_123"
    await db.commit()

    mock_data = {"campaign": {"id": "c1", "name": "Welcome Series", "status": "published"}}
    with patch("crm.routers.ghl_campaigns.fetch_campaign", new_callable=AsyncMock, return_value=mock_data):
        response = await client.get(f"/loc/{location.slug}/campaigns/c1")
    assert response.status_code == 200
    assert "Welcome Series" in response.text


@pytest.mark.asyncio
async def test_campaign_detail_no_ghl(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/campaigns/c1")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_campaign_detail_api_error(client: AsyncClient, location: Location, db):
    location.ghl_location_id = "ghl_loc_123"
    await db.commit()

    with patch("crm.routers.ghl_campaigns.fetch_campaign", new_callable=AsyncMock, side_effect=Exception("err")):
        response = await client.get(f"/loc/{location.slug}/campaigns/c1")
    assert response.status_code == 200
    assert "Failed" in response.text
