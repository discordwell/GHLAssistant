"""Test model creation and relationships."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from crm.models.contact import Contact
from crm.models.tag import Tag, ContactTag
from crm.models.pipeline import Pipeline, PipelineStage
from crm.models.opportunity import Opportunity
from crm.models.note import Note
from crm.models.task import Task
from crm.models.activity import Activity
from crm.models.custom_field import CustomFieldDefinition, CustomFieldValue
from crm.models.custom_value import CustomValue
from crm.models.location import Location


@pytest.mark.asyncio
async def test_create_location(db: AsyncSession):
    loc = Location(name="Acme Corp", slug="acme-corp")
    db.add(loc)
    await db.commit()
    result = await db.execute(select(Location).where(Location.slug == "acme-corp"))
    fetched = result.scalar_one()
    assert fetched.name == "Acme Corp"


@pytest.mark.asyncio
async def test_create_contact(db: AsyncSession, location: Location):
    contact = Contact(
        location_id=location.id,
        first_name="John",
        last_name="Doe",
        email="john@example.com",
    )
    db.add(contact)
    await db.commit()
    assert contact.full_name == "John Doe"


@pytest.mark.asyncio
async def test_create_tag_and_assign(db: AsyncSession, location: Location):
    contact = Contact(location_id=location.id, first_name="Jane")
    tag = Tag(location_id=location.id, name="VIP")
    db.add_all([contact, tag])
    await db.commit()

    ct = ContactTag(contact_id=contact.id, tag_id=tag.id)
    db.add(ct)
    await db.commit()

    result = await db.execute(
        select(ContactTag).where(ContactTag.contact_id == contact.id)
    )
    assert result.scalar_one() is not None


@pytest.mark.asyncio
async def test_create_pipeline_with_stages(db: AsyncSession, location: Location):
    pipeline = Pipeline(location_id=location.id, name="Sales")
    db.add(pipeline)
    await db.flush()

    s1 = PipelineStage(pipeline_id=pipeline.id, name="Lead", position=0)
    s2 = PipelineStage(pipeline_id=pipeline.id, name="Qualified", position=1)
    db.add_all([s1, s2])
    await db.commit()

    result = await db.execute(
        select(PipelineStage).where(PipelineStage.pipeline_id == pipeline.id)
    )
    stages = list(result.scalars().all())
    assert len(stages) == 2


@pytest.mark.asyncio
async def test_create_opportunity(db: AsyncSession, location: Location):
    pipeline = Pipeline(location_id=location.id, name="Deals")
    db.add(pipeline)
    await db.flush()

    stage = PipelineStage(pipeline_id=pipeline.id, name="New", position=0)
    db.add(stage)
    await db.flush()

    opp = Opportunity(
        location_id=location.id,
        name="Big Deal",
        pipeline_id=pipeline.id,
        stage_id=stage.id,
        monetary_value=10000.0,
    )
    db.add(opp)
    await db.commit()
    assert opp.status == "open"
    assert opp.monetary_value == 10000.0


@pytest.mark.asyncio
async def test_create_note(db: AsyncSession, location: Location):
    contact = Contact(location_id=location.id, first_name="Bob")
    db.add(contact)
    await db.flush()

    note = Note(location_id=location.id, contact_id=contact.id, body="Test note")
    db.add(note)
    await db.commit()
    assert note.body == "Test note"


@pytest.mark.asyncio
async def test_create_task(db: AsyncSession, location: Location):
    task = Task(location_id=location.id, title="Follow up", priority=1)
    db.add(task)
    await db.commit()
    assert task.status == "pending"
    assert task.priority == 1


@pytest.mark.asyncio
async def test_create_activity(db: AsyncSession, location: Location):
    activity = Activity(
        location_id=location.id,
        entity_type="contact",
        entity_id=uuid.uuid4(),
        action="created",
        description="Test activity",
    )
    db.add(activity)
    await db.commit()
    assert activity.action == "created"
