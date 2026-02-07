"""Tests for GHL Funnels routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from crm.models.location import Location


@pytest.mark.asyncio
async def test_funnels_page_no_ghl_location(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/funnels/")
    assert response.status_code == 200
    assert "GHL" in response.text or "No GHL" in response.text


@pytest.mark.asyncio
async def test_funnels_page_ghl_linked(client: AsyncClient, location: Location, db):
    location.ghl_location_id = "ghl_loc_123"
    await db.commit()

    mock_data = {"funnels": [{"_id": "fn1", "name": "Sales Funnel", "steps": [{"id": "s1"}]}]}
    with patch("crm.routers.ghl_funnels.fetch_funnels", new_callable=AsyncMock, return_value=mock_data):
        response = await client.get(f"/loc/{location.slug}/funnels/")
    assert response.status_code == 200
    assert "Sales Funnel" in response.text


@pytest.mark.asyncio
async def test_funnels_page_api_error(client: AsyncClient, location: Location, db):
    location.ghl_location_id = "ghl_loc_123"
    await db.commit()

    with patch("crm.routers.ghl_funnels.fetch_funnels", new_callable=AsyncMock, side_effect=Exception("err")):
        response = await client.get(f"/loc/{location.slug}/funnels/")
    assert response.status_code == 200
    assert "Failed" in response.text


@pytest.mark.asyncio
async def test_funnel_pages(client: AsyncClient, location: Location, db):
    location.ghl_location_id = "ghl_loc_123"
    await db.commit()

    mock_data = {"pages": [{"_id": "p1", "name": "Landing Page", "path": "landing"}]}
    with patch("crm.routers.ghl_funnels.fetch_funnel_pages", new_callable=AsyncMock, return_value=mock_data):
        response = await client.get(f"/loc/{location.slug}/funnels/fn1/pages")
    assert response.status_code == 200
    assert "Landing Page" in response.text


@pytest.mark.asyncio
async def test_funnel_pages_no_ghl(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/funnels/fn1/pages")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_funnel_pages_api_error(client: AsyncClient, location: Location, db):
    location.ghl_location_id = "ghl_loc_123"
    await db.commit()

    with patch("crm.routers.ghl_funnels.fetch_funnel_pages", new_callable=AsyncMock, side_effect=Exception("err")):
        response = await client.get(f"/loc/{location.slug}/funnels/fn1/pages")
    assert response.status_code == 200
    assert "Failed" in response.text
