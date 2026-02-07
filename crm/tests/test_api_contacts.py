"""Test contact API routes."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from crm.models.location import Location


@pytest.mark.asyncio
async def test_location_list_page(client: AsyncClient):
    response = await client.get("/locations/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_create_location(client: AsyncClient):
    response = await client.post("/locations/", data={
        "name": "API Test Location",
        "timezone": "UTC",
    }, follow_redirects=False)
    assert response.status_code == 303


@pytest.mark.asyncio
async def test_contact_list_page(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/contacts/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_create_contact_via_form(client: AsyncClient, location: Location):
    response = await client.post(f"/loc/{location.slug}/contacts/", data={
        "first_name": "API",
        "last_name": "User",
        "email": "api@test.com",
    }, follow_redirects=False)
    assert response.status_code == 303


@pytest.mark.asyncio
async def test_contact_new_form(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/contacts/new")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_dashboard(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_tags_page(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/tags/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_create_tag(client: AsyncClient, location: Location):
    response = await client.post(f"/loc/{location.slug}/tags/", data={
        "name": "test-tag",
    }, follow_redirects=False)
    assert response.status_code == 303


@pytest.mark.asyncio
async def test_tasks_page(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/tasks/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_custom_fields_page(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/custom-fields/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_sync_page(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/sync/")
    assert response.status_code == 200
