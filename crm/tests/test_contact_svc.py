"""Test contact service."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from crm.models.location import Location
from crm.models.tag import Tag
from crm.services import contact_svc, tag_svc


@pytest.mark.asyncio
async def test_create_and_get_contact(db: AsyncSession, location: Location):
    contact = await contact_svc.create_contact(
        db, location.id, first_name="Alice", last_name="Smith", email="alice@test.com"
    )
    assert contact.full_name == "Alice Smith"

    fetched = await contact_svc.get_contact(db, contact.id)
    assert fetched is not None
    assert fetched.email == "alice@test.com"


@pytest.mark.asyncio
async def test_list_contacts_with_search(db: AsyncSession, location: Location):
    await contact_svc.create_contact(db, location.id, first_name="Bob", email="bob@test.com")
    await contact_svc.create_contact(db, location.id, first_name="Carol", email="carol@test.com")

    contacts, total = await contact_svc.list_contacts(db, location.id, search="bob")
    assert total == 1
    assert contacts[0].first_name == "Bob"


@pytest.mark.asyncio
async def test_list_contacts_pagination(db: AsyncSession, location: Location):
    for i in range(5):
        await contact_svc.create_contact(db, location.id, first_name=f"User{i}")

    contacts, total = await contact_svc.list_contacts(db, location.id, limit=2)
    assert total == 5
    assert len(contacts) == 2


@pytest.mark.asyncio
async def test_update_contact(db: AsyncSession, location: Location):
    contact = await contact_svc.create_contact(db, location.id, first_name="Dan")
    updated = await contact_svc.update_contact(db, contact.id, last_name="Brown")
    assert updated.last_name == "Brown"


@pytest.mark.asyncio
async def test_delete_contact(db: AsyncSession, location: Location):
    contact = await contact_svc.create_contact(db, location.id, first_name="Eve")
    result = await contact_svc.delete_contact(db, contact.id)
    assert result is True

    fetched = await contact_svc.get_contact(db, contact.id)
    assert fetched is None


@pytest.mark.asyncio
async def test_tag_assignment(db: AsyncSession, location: Location):
    contact = await contact_svc.create_contact(db, location.id, first_name="Frank")
    tag = await tag_svc.create_tag(db, location.id, "VIP")

    added = await contact_svc.add_tag_to_contact(db, contact.id, tag.id)
    assert added is True

    # Duplicate should return False
    added_again = await contact_svc.add_tag_to_contact(db, contact.id, tag.id)
    assert added_again is False

    removed = await contact_svc.remove_tag_from_contact(db, contact.id, tag.id)
    assert removed is True


@pytest.mark.asyncio
async def test_list_contacts_by_tag(db: AsyncSession, location: Location):
    c1 = await contact_svc.create_contact(db, location.id, first_name="Tagged")
    c2 = await contact_svc.create_contact(db, location.id, first_name="Untagged")
    tag = await tag_svc.create_tag(db, location.id, "Special")
    await contact_svc.add_tag_to_contact(db, c1.id, tag.id)

    contacts, total = await contact_svc.list_contacts(db, location.id, tag_name="Special")
    assert total == 1
    assert contacts[0].first_name == "Tagged"
