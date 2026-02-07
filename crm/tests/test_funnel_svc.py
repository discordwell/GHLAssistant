"""Test funnel service."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from crm.models.funnel import FunnelPage
from crm.models.location import Location
from crm.services import funnel_svc


@pytest.mark.asyncio
async def test_create_and_list_funnels(db: AsyncSession, location: Location):
    await funnel_svc.create_funnel(db, location.id, name="Sales Funnel")
    await funnel_svc.create_funnel(db, location.id, name="Onboarding Funnel")

    funnels = await funnel_svc.list_funnels(db, location.id)
    assert len(funnels) == 2
    names = [f.name for f in funnels]
    assert "Sales Funnel" in names
    assert "Onboarding Funnel" in names


@pytest.mark.asyncio
async def test_get_funnel(db: AsyncSession, location: Location):
    funnel = await funnel_svc.create_funnel(
        db, location.id, name="My Funnel", description="A test funnel"
    )
    fetched = await funnel_svc.get_funnel(db, funnel.id)
    assert fetched is not None
    assert fetched.name == "My Funnel"
    assert fetched.description == "A test funnel"
    assert fetched.is_published is False


@pytest.mark.asyncio
async def test_update_funnel(db: AsyncSession, location: Location):
    funnel = await funnel_svc.create_funnel(db, location.id, name="Old Funnel")
    updated = await funnel_svc.update_funnel(
        db, funnel.id, name="New Funnel", is_published=True
    )
    assert updated is not None
    assert updated.name == "New Funnel"
    assert updated.is_published is True


@pytest.mark.asyncio
async def test_delete_funnel(db: AsyncSession, location: Location):
    funnel = await funnel_svc.create_funnel(db, location.id, name="Delete Me")
    result = await funnel_svc.delete_funnel(db, funnel.id)
    assert result is True

    fetched = await funnel_svc.get_funnel(db, funnel.id)
    assert fetched is None


@pytest.mark.asyncio
async def test_add_page(db: AsyncSession, location: Location):
    funnel = await funnel_svc.create_funnel(db, location.id, name="Page Funnel")
    p1 = await funnel_svc.add_page(
        db, funnel.id, name="Landing", url_slug="landing",
        content_html="<h1>Welcome</h1>", is_published=True
    )
    p2 = await funnel_svc.add_page(
        db, funnel.id, name="Thank You", url_slug="thank-you",
        content_html="<h1>Thanks</h1>", is_published=True
    )

    assert p1.position == 0
    assert p2.position == 1
    assert p1.name == "Landing"
    assert p1.url_slug == "landing"
    assert p1.is_published is True


@pytest.mark.asyncio
async def test_delete_page(db: AsyncSession, location: Location):
    funnel = await funnel_svc.create_funnel(db, location.id, name="Del Page Funnel")
    page = await funnel_svc.add_page(
        db, funnel.id, name="Remove", url_slug="remove", content_html=""
    )
    result = await funnel_svc.delete_page(db, page.id)
    assert result is True

    # Verify page is gone
    fetched = await funnel_svc.get_funnel(db, funnel.id)
    assert fetched is not None
    assert len(fetched.pages) == 0


@pytest.mark.asyncio
async def test_reorder_pages(db: AsyncSession, location: Location):
    funnel = await funnel_svc.create_funnel(db, location.id, name="Reorder Funnel")
    p1 = await funnel_svc.add_page(
        db, funnel.id, name="Page A", url_slug="a", content_html=""
    )
    p2 = await funnel_svc.add_page(
        db, funnel.id, name="Page B", url_slug="b", content_html=""
    )
    p3 = await funnel_svc.add_page(
        db, funnel.id, name="Page C", url_slug="c", content_html=""
    )

    # Reverse the order: C, B, A
    await funnel_svc.reorder_pages(db, funnel.id, [str(p3.id), str(p2.id), str(p1.id)])

    fetched = await funnel_svc.get_funnel(db, funnel.id)
    assert fetched is not None
    pages = sorted(fetched.pages, key=lambda p: p.position)
    assert pages[0].name == "Page C"
    assert pages[1].name == "Page B"
    assert pages[2].name == "Page A"


@pytest.mark.asyncio
async def test_get_public_page(db: AsyncSession, location: Location):
    funnel = await funnel_svc.create_funnel(db, location.id, name="Public Funnel")
    await funnel_svc.add_page(
        db, funnel.id, name="Public Page", url_slug="public",
        content_html="<p>Public content</p>", is_published=True
    )

    page = await funnel_svc.get_public_page(db, funnel.id, "public")
    assert page is not None
    assert page.name == "Public Page"
    assert page.content_html == "<p>Public content</p>"


@pytest.mark.asyncio
async def test_get_public_page_unpublished_returns_none(db: AsyncSession, location: Location):
    funnel = await funnel_svc.create_funnel(db, location.id, name="Draft Funnel")
    await funnel_svc.add_page(
        db, funnel.id, name="Draft Page", url_slug="draft",
        content_html="<p>Draft</p>", is_published=False
    )

    page = await funnel_svc.get_public_page(db, funnel.id, "draft")
    assert page is None


@pytest.mark.asyncio
async def test_delete_funnel_cascades_pages(db: AsyncSession, location: Location):
    funnel = await funnel_svc.create_funnel(db, location.id, name="Cascade Funnel")
    p1 = await funnel_svc.add_page(
        db, funnel.id, name="Page 1", url_slug="p1", content_html=""
    )
    p2 = await funnel_svc.add_page(
        db, funnel.id, name="Page 2", url_slug="p2", content_html=""
    )

    page_ids = [p1.id, p2.id]
    await funnel_svc.delete_funnel(db, funnel.id)

    # Verify pages are gone
    for pid in page_ids:
        stmt = select(FunnelPage).where(FunnelPage.id == pid)
        result = (await db.execute(stmt)).scalar_one_or_none()
        assert result is None
