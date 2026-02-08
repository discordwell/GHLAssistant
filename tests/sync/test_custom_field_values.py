"""Sync tests for custom field value import/export."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from crm.models.base import Base
from crm.models.contact import Contact
from crm.models.custom_field import CustomFieldDefinition, CustomFieldValue
from crm.models.location import Location
from crm.models.tag import Tag
from crm.sync.exporter import export_contacts
from crm.sync.importer import import_contacts


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def location(db: AsyncSession) -> Location:
    loc = Location(
        id=uuid.uuid4(),
        name="Test Location",
        slug="test-location",
        timezone="UTC",
        ghl_location_id="ghl_loc_123",
    )
    db.add(loc)
    await db.commit()
    await db.refresh(loc)
    return loc


@pytest.mark.asyncio
async def test_import_contacts_upserts_custom_field_values(db: AsyncSession, location: Location):
    defn = CustomFieldDefinition(
        location_id=location.id,
        name="Lead Score",
        field_key="lead_score",
        data_type="number",
        entity_type="contact",
        ghl_id="ghl_field_1",
        ghl_location_id=location.ghl_location_id,
    )
    db.add(defn)
    await db.commit()

    contacts_data = [
        {
            "id": "ghl_contact_1",
            "firstName": "Jane",
            "email": "jane@example.com",
            "customFields": [{"id": "ghl_field_1", "value": "42"}],
        }
    ]

    result, contact_map = await import_contacts(db, location, contacts_data)
    assert result.created == 1
    assert "ghl_contact_1" in contact_map

    contact = (await db.execute(select(Contact))).scalar_one()
    cfv = (await db.execute(select(CustomFieldValue))).scalar_one()

    assert cfv.definition_id == defn.id
    assert cfv.entity_id == contact.id
    assert cfv.entity_type == "contact"
    assert cfv.value_number == 42.0

    # Update existing value
    contacts_data[0]["customFields"][0]["value"] = "43"
    result2, _ = await import_contacts(db, location, contacts_data)
    assert result2.updated == 1

    cfv2 = (await db.execute(select(CustomFieldValue))).scalar_one()
    assert cfv2.value_number == 43.0


class _DummyContacts:
    def __init__(self):
        self.updated: list[tuple[str, dict]] = []

    async def update(self, contact_id: str, **data):
        self.updated.append((contact_id, data))
        return {}


class _DummyGHL:
    def __init__(self):
        self.contacts = _DummyContacts()


@pytest.mark.asyncio
async def test_export_contacts_includes_tags_and_custom_fields(db: AsyncSession, location: Location):
    defn = CustomFieldDefinition(
        location_id=location.id,
        name="Custom Text",
        field_key="custom_text",
        data_type="text",
        entity_type="contact",
        ghl_id="ghl_field_txt",
        ghl_location_id=location.ghl_location_id,
    )
    contact = Contact(
        location_id=location.id,
        first_name="Alex",
        email="alex@example.com",
        ghl_id="ghl_contact_99",
        ghl_location_id=location.ghl_location_id,
    )
    tag = Tag(
        location_id=location.id,
        name="vip",
        ghl_location_id=location.ghl_location_id,
    )
    contact.tags.append(tag)
    db.add_all([defn, contact, tag])
    await db.commit()
    await db.refresh(contact)

    cfv = CustomFieldValue(
        definition_id=defn.id,
        entity_id=contact.id,
        entity_type="contact",
        value_text="hello",
    )
    db.add(cfv)
    await db.commit()

    ghl = _DummyGHL()
    result = await export_contacts(db, location, ghl)
    assert result.updated == 1
    assert len(ghl.contacts.updated) == 1

    _, payload = ghl.contacts.updated[0]
    assert payload["locationId"] == location.ghl_location_id
    assert payload["tags"] == ["vip"]
    assert "customFields" in payload

    item = payload["customFields"][0]
    assert item["id"] == "ghl_field_txt"
    assert item["fieldKey"] == "custom_text"
    assert item["value"] == "hello"

