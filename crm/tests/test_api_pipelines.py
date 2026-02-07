"""Test pipeline API routes."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from crm.models.location import Location


@pytest.mark.asyncio
async def test_pipeline_list_page(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/pipelines/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_pipeline_new_form(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/pipelines/new")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_create_pipeline_via_form(client: AsyncClient, location: Location):
    response = await client.post(f"/loc/{location.slug}/pipelines/", data={
        "name": "Test Pipeline",
        "description": "A test pipeline",
        "stages": "Lead, Qualified, Won, Lost",
    }, follow_redirects=False)
    assert response.status_code == 303


@pytest.mark.asyncio
async def test_create_task_via_form(client: AsyncClient, location: Location):
    response = await client.post(f"/loc/{location.slug}/tasks/", data={
        "title": "Follow up with client",
        "priority": "1",
    }, follow_redirects=False)
    assert response.status_code == 303
