"""Test GHL importer."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from crm.models.location import Location
from crm.models.tag import Tag
from crm.models.contact import Contact
from crm.models.pipeline import Pipeline, PipelineStage
from crm.sync.importer import import_tags, import_contacts, import_pipelines


@pytest.mark.asyncio
async def test_import_tags_creates_new(db: AsyncSession, location: Location):
    tags_data = [
        {"id": "ghl-tag-1", "name": "Lead"},
        {"id": "ghl-tag-2", "name": "Customer"},
    ]
    result = await import_tags(db, location, tags_data)
    assert result.created == 2
    assert result.updated == 0


@pytest.mark.asyncio
async def test_import_tags_updates_existing(db: AsyncSession, location: Location):
    tag = Tag(location_id=location.id, name="Old Name", ghl_id="ghl-tag-x")
    db.add(tag)
    await db.commit()

    tags_data = [{"id": "ghl-tag-x", "name": "New Name"}]
    result = await import_tags(db, location, tags_data)
    assert result.updated == 1

    await db.refresh(tag)
    assert tag.name == "New Name"


@pytest.mark.asyncio
async def test_import_contacts_creates_new(db: AsyncSession, location: Location):
    contacts_data = [
        {"id": "ghl-c-1", "firstName": "Alice", "lastName": "Smith", "email": "alice@test.com"},
        {"id": "ghl-c-2", "firstName": "Bob", "email": "bob@test.com"},
    ]
    result, contact_map = await import_contacts(db, location, contacts_data)
    assert result.created == 2
    assert "ghl-c-1" in contact_map


@pytest.mark.asyncio
async def test_import_contacts_dedup_by_email(db: AsyncSession, location: Location):
    # Pre-create a contact with matching email
    existing = Contact(location_id=location.id, first_name="Existing", email="existing@test.com")
    db.add(existing)
    await db.commit()

    contacts_data = [
        {"id": "ghl-c-dup", "firstName": "Updated", "email": "existing@test.com"},
    ]
    result, _ = await import_contacts(db, location, contacts_data)
    assert result.updated == 1

    await db.refresh(existing)
    assert existing.first_name == "Updated"
    assert existing.ghl_id == "ghl-c-dup"


@pytest.mark.asyncio
async def test_import_pipelines_with_stages(db: AsyncSession, location: Location):
    pipelines_data = [
        {
            "id": "ghl-p-1",
            "name": "Sales",
            "stages": [
                {"id": "ghl-s-1", "name": "Lead"},
                {"id": "ghl-s-2", "name": "Qualified"},
                {"id": "ghl-s-3", "name": "Won"},
            ],
        }
    ]
    result, stage_map = await import_pipelines(db, location, pipelines_data)
    assert result.created == 1
    assert len(stage_map) == 3
    assert "ghl-s-1" in stage_map
