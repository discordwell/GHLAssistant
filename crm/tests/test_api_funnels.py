"""Test funnel API routes."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from crm.models.funnel import Funnel, FunnelPage
from crm.models.location import Location


@pytest.mark.asyncio
async def test_funnels_list_page(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/funnels/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_funnels_new_page(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/funnels/new")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_funnels_create(client: AsyncClient, location: Location):
    response = await client.post(
        f"/loc/{location.slug}/funnels/",
        data={"name": "Sales Funnel"},
        follow_redirects=False,
    )
    assert response.status_code == 303


@pytest.mark.asyncio
async def test_funnels_detail(
    client: AsyncClient, db: AsyncSession, location: Location
):
    funnel = Funnel(
        location_id=location.id,
        name="Detail Funnel",
    )
    db.add(funnel)
    await db.commit()
    await db.refresh(funnel)

    response = await client.get(f"/loc/{location.slug}/funnels/{funnel.id}")
    assert response.status_code == 200
    assert "Detail Funnel" in response.text


@pytest.mark.asyncio
async def test_funnels_add_page(
    client: AsyncClient, db: AsyncSession, location: Location
):
    funnel = Funnel(
        location_id=location.id,
        name="Page Funnel",
    )
    db.add(funnel)
    await db.commit()
    await db.refresh(funnel)

    response = await client.post(
        f"/loc/{location.slug}/funnels/{funnel.id}/pages",
        data={
            "name": "Landing Page",
            "url_slug": "landing",
            "content_html": "<h1>Welcome</h1>",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


@pytest.mark.asyncio
async def test_funnels_delete_page(
    client: AsyncClient, db: AsyncSession, location: Location
):
    funnel = Funnel(
        location_id=location.id,
        name="Del Page Funnel",
    )
    db.add(funnel)
    await db.commit()
    await db.refresh(funnel)

    page = FunnelPage(
        funnel_id=funnel.id,
        name="To Delete",
        url_slug="delete-me",
        position=0,
    )
    db.add(page)
    await db.commit()
    await db.refresh(page)

    response = await client.post(
        f"/loc/{location.slug}/funnels/{funnel.id}/pages/{page.id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 303


@pytest.mark.asyncio
async def test_funnels_delete(
    client: AsyncClient, db: AsyncSession, location: Location
):
    funnel = Funnel(
        location_id=location.id,
        name="To Delete Funnel",
    )
    db.add(funnel)
    await db.commit()
    await db.refresh(funnel)

    response = await client.post(
        f"/loc/{location.slug}/funnels/{funnel.id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 303


@pytest.mark.asyncio
async def test_funnels_public_page_get(
    client: AsyncClient, db: AsyncSession, location: Location
):
    funnel = Funnel(
        location_id=location.id,
        name="Public Funnel",
        is_published=True,
    )
    db.add(funnel)
    await db.commit()
    await db.refresh(funnel)

    page = FunnelPage(
        funnel_id=funnel.id,
        name="Public Page",
        url_slug="welcome",
        content_html="<h1>Welcome to our funnel</h1>",
        position=0,
        is_published=True,
    )
    db.add(page)
    await db.commit()
    await db.refresh(page)

    response = await client.get(f"/p/{funnel.id}/welcome")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_funnels_public_page_not_found(client: AsyncClient):
    fake_id = uuid.uuid4()
    response = await client.get(f"/p/{fake_id}/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_funnels_list_empty(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/funnels/")
    assert response.status_code == 200
