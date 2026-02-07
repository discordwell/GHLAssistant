"""Test campaign service."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from crm.models.contact import Contact
from crm.models.location import Location
from crm.services import campaign_svc


async def _make_contact(db: AsyncSession, location: Location, name: str = "Test") -> Contact:
    contact = Contact(location_id=location.id, first_name=name)
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return contact


@pytest.mark.asyncio
async def test_create_and_list_campaigns(db: AsyncSession, location: Location):
    await campaign_svc.create_campaign(db, location.id, name="Welcome Series")
    await campaign_svc.create_campaign(db, location.id, name="Re-engagement")

    campaigns = await campaign_svc.list_campaigns(db, location.id)
    assert len(campaigns) == 2
    names = [c.name for c in campaigns]
    assert "Welcome Series" in names
    assert "Re-engagement" in names


@pytest.mark.asyncio
async def test_get_campaign(db: AsyncSession, location: Location):
    campaign = await campaign_svc.create_campaign(
        db, location.id, name="Test Campaign", description="A test"
    )
    fetched = await campaign_svc.get_campaign(db, campaign.id)
    assert fetched is not None
    assert fetched.name == "Test Campaign"
    assert fetched.description == "A test"
    assert fetched.status == "draft"


@pytest.mark.asyncio
async def test_update_campaign(db: AsyncSession, location: Location):
    campaign = await campaign_svc.create_campaign(db, location.id, name="Old Campaign")
    updated = await campaign_svc.update_campaign(
        db, campaign.id, name="New Campaign", status="active"
    )
    assert updated is not None
    assert updated.name == "New Campaign"
    assert updated.status == "active"


@pytest.mark.asyncio
async def test_delete_campaign(db: AsyncSession, location: Location):
    campaign = await campaign_svc.create_campaign(db, location.id, name="Delete Me")
    result = await campaign_svc.delete_campaign(db, campaign.id)
    assert result is True

    fetched = await campaign_svc.get_campaign(db, campaign.id)
    assert fetched is None


@pytest.mark.asyncio
async def test_add_step(db: AsyncSession, location: Location):
    campaign = await campaign_svc.create_campaign(db, location.id, name="Step Campaign")
    step = await campaign_svc.add_step(
        db, campaign.id, step_type="email", subject="Welcome!", body="Hello there"
    )
    assert step.position == 0
    assert step.step_type == "email"
    assert step.subject == "Welcome!"
    assert step.body == "Hello there"


@pytest.mark.asyncio
async def test_add_multiple_steps(db: AsyncSession, location: Location):
    campaign = await campaign_svc.create_campaign(db, location.id, name="Multi Step")
    s1 = await campaign_svc.add_step(db, campaign.id, step_type="email", subject="Step 1")
    s2 = await campaign_svc.add_step(db, campaign.id, step_type="sms", body="Follow up")
    s3 = await campaign_svc.add_step(db, campaign.id, step_type="email", subject="Step 3")

    assert s1.position == 0
    assert s2.position == 1
    assert s3.position == 2


@pytest.mark.asyncio
async def test_delete_step(db: AsyncSession, location: Location):
    campaign = await campaign_svc.create_campaign(db, location.id, name="Del Step")
    step = await campaign_svc.add_step(db, campaign.id, step_type="sms", body="Remove")
    result = await campaign_svc.delete_step(db, step.id)
    assert result is True

    fetched = await campaign_svc.get_campaign(db, campaign.id)
    assert fetched is not None
    assert len(fetched.steps) == 0


@pytest.mark.asyncio
async def test_enroll_contact(db: AsyncSession, location: Location):
    campaign = await campaign_svc.create_campaign(db, location.id, name="Enroll Campaign")
    contact = await _make_contact(db, location, name="Enrollee")

    enrollment = await campaign_svc.enroll_contact(
        db, location.id, campaign.id, contact.id
    )
    assert enrollment is not None
    assert enrollment.contact_id == contact.id
    assert enrollment.campaign_id == campaign.id
    assert enrollment.status == "active"
    assert enrollment.current_step == 0


@pytest.mark.asyncio
async def test_enroll_contact_duplicate_returns_none(db: AsyncSession, location: Location):
    campaign = await campaign_svc.create_campaign(db, location.id, name="Dup Campaign")
    contact = await _make_contact(db, location, name="Dup Contact")

    first = await campaign_svc.enroll_contact(
        db, location.id, campaign.id, contact.id
    )
    assert first is not None

    second = await campaign_svc.enroll_contact(
        db, location.id, campaign.id, contact.id
    )
    assert second is None


@pytest.mark.asyncio
async def test_unenroll_contact(db: AsyncSession, location: Location):
    campaign = await campaign_svc.create_campaign(db, location.id, name="Unenroll Campaign")
    contact = await _make_contact(db, location, name="Unenrollee")
    enrollment = await campaign_svc.enroll_contact(
        db, location.id, campaign.id, contact.id
    )
    assert enrollment is not None

    result = await campaign_svc.unenroll_contact(db, enrollment.id)
    assert result is True

    # Verify enrollment is gone by re-fetching campaign
    fetched = await campaign_svc.get_campaign(db, campaign.id)
    assert fetched is not None
    assert len(fetched.enrollments) == 0


@pytest.mark.asyncio
async def test_trigger_next_step(db: AsyncSession, location: Location):
    campaign = await campaign_svc.create_campaign(db, location.id, name="Trigger Campaign")
    await campaign_svc.add_step(db, campaign.id, step_type="email", subject="Step 1")
    await campaign_svc.add_step(db, campaign.id, step_type="sms", body="Step 2")

    contact = await _make_contact(db, location, name="Trigger Contact")
    await campaign_svc.enroll_contact(db, location.id, campaign.id, contact.id)

    # First trigger: advance from step 0 to step 1
    result1 = await campaign_svc.trigger_next_step(db, campaign.id)
    assert result1["advanced"] == 1
    assert result1["completed"] == 0

    # Second trigger: advance from step 1 to step 2 (completed)
    result2 = await campaign_svc.trigger_next_step(db, campaign.id)
    assert result2["advanced"] == 1
    assert result2["completed"] == 1


@pytest.mark.asyncio
async def test_trigger_no_steps(db: AsyncSession, location: Location):
    campaign = await campaign_svc.create_campaign(db, location.id, name="Empty Campaign")
    result = await campaign_svc.trigger_next_step(db, campaign.id)
    assert "error" in result
    assert result["error"] == "No steps configured"
