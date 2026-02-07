"""Test campaign API routes."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from crm.models.campaign import Campaign, CampaignStep
from crm.models.contact import Contact
from crm.models.location import Location


@pytest.mark.asyncio
async def test_campaigns_list_page(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/campaigns/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_campaigns_new_page(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/campaigns/new")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_campaigns_create(client: AsyncClient, location: Location):
    response = await client.post(
        f"/loc/{location.slug}/campaigns/",
        data={"name": "Welcome Series"},
        follow_redirects=False,
    )
    assert response.status_code == 303


@pytest.mark.asyncio
async def test_campaigns_detail(
    client: AsyncClient, db: AsyncSession, location: Location
):
    campaign = Campaign(
        location_id=location.id,
        name="Detail Campaign",
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)

    response = await client.get(f"/loc/{location.slug}/campaigns/{campaign.id}")
    assert response.status_code == 200
    assert "Detail Campaign" in response.text


@pytest.mark.asyncio
async def test_campaigns_add_step(
    client: AsyncClient, db: AsyncSession, location: Location
):
    campaign = Campaign(
        location_id=location.id,
        name="Step Campaign",
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)

    response = await client.post(
        f"/loc/{location.slug}/campaigns/{campaign.id}/steps",
        data={
            "step_type": "email",
            "subject": "Hello",
            "body": "Welcome",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


@pytest.mark.asyncio
async def test_campaigns_delete_step(
    client: AsyncClient, db: AsyncSession, location: Location
):
    campaign = Campaign(
        location_id=location.id,
        name="Del Step Campaign",
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)

    step = CampaignStep(
        campaign_id=campaign.id,
        step_type="email",
        subject="To Delete",
        body="Goodbye",
        position=0,
    )
    db.add(step)
    await db.commit()
    await db.refresh(step)

    response = await client.post(
        f"/loc/{location.slug}/campaigns/{campaign.id}/steps/{step.id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 303


@pytest.mark.asyncio
async def test_campaigns_enroll(
    client: AsyncClient, db: AsyncSession, location: Location
):
    campaign = Campaign(
        location_id=location.id,
        name="Enroll Campaign",
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)

    contact = Contact(
        location_id=location.id,
        first_name="Enroll",
        last_name="Person",
        email="enroll@test.com",
    )
    db.add(contact)
    await db.commit()
    await db.refresh(contact)

    response = await client.post(
        f"/loc/{location.slug}/campaigns/{campaign.id}/enroll",
        data={"contact_id": str(contact.id)},
        follow_redirects=False,
    )
    assert response.status_code == 303


@pytest.mark.asyncio
async def test_campaigns_trigger_all(
    client: AsyncClient, db: AsyncSession, location: Location
):
    campaign = Campaign(
        location_id=location.id,
        name="Trigger Campaign",
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)

    response = await client.post(
        f"/loc/{location.slug}/campaigns/{campaign.id}/trigger-all",
        follow_redirects=False,
    )
    assert response.status_code == 303


@pytest.mark.asyncio
async def test_campaigns_delete(
    client: AsyncClient, db: AsyncSession, location: Location
):
    campaign = Campaign(
        location_id=location.id,
        name="To Delete Campaign",
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)

    response = await client.post(
        f"/loc/{location.slug}/campaigns/{campaign.id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 303


@pytest.mark.asyncio
async def test_campaigns_list_empty(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/campaigns/")
    assert response.status_code == 200
