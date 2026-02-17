"""Tests for the dashboard HTTP routes."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_home_returns_200(client):
    response = await client.get("/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_home_contains_app_cards(client):
    response = await client.get("/")
    html = response.text
    assert "CRM Platform" in html
    assert "Hiring Tool" in html
    assert "Workflows" in html


@pytest.mark.asyncio
async def test_home_contains_metrics(client):
    """Metrics from seeded data should appear in the page."""
    response = await client.get("/")
    html = response.text
    # Seeded: 5 contacts, 3 opportunities, 2 pipelines
    assert ">5<" in html  # contacts
    assert ">3<" in html  # opportunities


@pytest.mark.asyncio
async def test_home_contains_activity_feed(client):
    """Activity items should be rendered."""
    response = await client.get("/")
    html = response.text
    assert "Recent Activity" in html
    assert "crm" in html.lower()


@pytest.mark.asyncio
async def test_home_contains_cross_nav(client):
    """Cross-nav bar should be present."""
    response = await client.get("/")
    html = response.text
    assert "localhost:8023" in html
    assert "localhost:8020" in html
    assert "localhost:8021" in html
    assert "localhost:8022" in html


@pytest.mark.asyncio
async def test_home_contains_port_links(client):
    """App cards should link to the correct ports."""
    response = await client.get("/")
    html = response.text
    assert "http://localhost:8020" in html
    assert "http://localhost:8021" in html
    assert "http://localhost:8022" in html


@pytest.mark.asyncio
async def test_health_returns_json(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "services" in data
    assert "dashboard" in data["services"]
    assert data["services"]["dashboard"] == "ok"


@pytest.mark.asyncio
async def test_health_checks_all_services(client):
    """Health check should report on all 3 app databases."""
    response = await client.get("/health")
    data = response.json()
    services = data["services"]
    assert "crm" in services
    assert "workflows" in services
    assert "hiring" in services


@pytest.mark.asyncio
async def test_ready_endpoint(client):
    response = await client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "services" in data
