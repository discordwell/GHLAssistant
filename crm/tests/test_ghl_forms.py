"""Tests for GHL Forms routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from crm.models.location import Location


@pytest.mark.asyncio
async def test_forms_page_no_ghl_location(client: AsyncClient, location: Location):
    """Shows error when location has no ghl_location_id."""
    response = await client.get(f"/loc/{location.slug}/forms/")
    assert response.status_code == 200
    assert "GHL" in response.text or "No GHL" in response.text


@pytest.mark.asyncio
async def test_forms_page_ghl_linked(client: AsyncClient, location: Location, db):
    """Lists forms when GHL is linked."""
    location.ghl_location_id = "ghl_loc_123"
    await db.commit()

    mock_data = {"forms": [{"_id": "f1", "name": "Contact Form"}, {"_id": "f2", "name": "Survey"}]}
    with patch("crm.routers.ghl_forms.fetch_forms", new_callable=AsyncMock, return_value=mock_data):
        response = await client.get(f"/loc/{location.slug}/forms/")
    assert response.status_code == 200
    assert "Contact Form" in response.text
    assert "Survey" in response.text


@pytest.mark.asyncio
async def test_forms_page_ghl_not_linked_error(client: AsyncClient, location: Location, db):
    """Shows error when GHL token is invalid."""
    location.ghl_location_id = "ghl_loc_123"
    await db.commit()

    from crm.services.ghl_svc import GHLNotLinkedError
    with patch("crm.routers.ghl_forms.fetch_forms", new_callable=AsyncMock, side_effect=GHLNotLinkedError("No token")):
        response = await client.get(f"/loc/{location.slug}/forms/")
    assert response.status_code == 200
    assert "GHL" in response.text


@pytest.mark.asyncio
async def test_forms_page_api_error(client: AsyncClient, location: Location, db):
    """Shows error message on API failure."""
    location.ghl_location_id = "ghl_loc_123"
    await db.commit()

    with patch("crm.routers.ghl_forms.fetch_forms", new_callable=AsyncMock, side_effect=Exception("timeout")):
        response = await client.get(f"/loc/{location.slug}/forms/")
    assert response.status_code == 200
    assert "Failed" in response.text or "timeout" in response.text


@pytest.mark.asyncio
async def test_form_submissions(client: AsyncClient, location: Location, db):
    """Loads form submissions."""
    location.ghl_location_id = "ghl_loc_123"
    await db.commit()

    mock_data = {"submissions": [{"contactId": "c1", "createdAt": "2025-01-01T00:00:00Z"}], "meta": {"total": 1}}
    with patch("crm.routers.ghl_forms.fetch_form_submissions", new_callable=AsyncMock, return_value=mock_data):
        response = await client.get(f"/loc/{location.slug}/forms/f1/submissions")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_form_submissions_no_ghl(client: AsyncClient, location: Location):
    """Shows error for submissions when no GHL linked."""
    response = await client.get(f"/loc/{location.slug}/forms/f1/submissions")
    assert response.status_code == 200
