"""Test form service."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from crm.models.form import FormField
from crm.models.location import Location
from crm.services import form_svc


@pytest.mark.asyncio
async def test_create_and_list_forms(db: AsyncSession, location: Location):
    await form_svc.create_form(db, location.id, name="Contact Form")
    await form_svc.create_form(db, location.id, name="Signup Form")

    forms = await form_svc.list_forms(db, location.id)
    assert len(forms) == 2
    names = [f.name for f in forms]
    assert "Contact Form" in names
    assert "Signup Form" in names


@pytest.mark.asyncio
async def test_get_form(db: AsyncSession, location: Location):
    form = await form_svc.create_form(
        db, location.id, name="My Form", description="A test form"
    )
    fetched = await form_svc.get_form(db, form.id)
    assert fetched is not None
    assert fetched.name == "My Form"
    assert fetched.description == "A test form"
    assert fetched.is_active is True


@pytest.mark.asyncio
async def test_update_form(db: AsyncSession, location: Location):
    form = await form_svc.create_form(db, location.id, name="Old Name")
    updated = await form_svc.update_form(db, form.id, name="New Name", is_active=False)
    assert updated is not None
    assert updated.name == "New Name"
    assert updated.is_active is False


@pytest.mark.asyncio
async def test_delete_form(db: AsyncSession, location: Location):
    form = await form_svc.create_form(db, location.id, name="Delete Me")
    result = await form_svc.delete_form(db, form.id)
    assert result is True

    fetched = await form_svc.get_form(db, form.id)
    assert fetched is None


@pytest.mark.asyncio
async def test_add_field(db: AsyncSession, location: Location):
    form = await form_svc.create_form(db, location.id, name="Field Form")
    f1 = await form_svc.add_field(db, form.id, label="Name", field_type="text")
    f2 = await form_svc.add_field(db, form.id, label="Email", field_type="email")

    # Auto-position: first field is 0, second is 1
    assert f1.position == 0
    assert f2.position == 1
    assert f1.label == "Name"
    assert f2.field_type == "email"


@pytest.mark.asyncio
async def test_delete_field(db: AsyncSession, location: Location):
    form = await form_svc.create_form(db, location.id, name="Del Field Form")
    field = await form_svc.add_field(db, form.id, label="Remove Me", field_type="text")
    result = await form_svc.delete_field(db, field.id)
    assert result is True

    # Verify field is gone
    fetched = await form_svc.get_form(db, form.id)
    assert fetched is not None
    assert len(fetched.fields) == 0


@pytest.mark.asyncio
async def test_reorder_fields(db: AsyncSession, location: Location):
    form = await form_svc.create_form(db, location.id, name="Reorder Form")
    f1 = await form_svc.add_field(db, form.id, label="A", field_type="text")
    f2 = await form_svc.add_field(db, form.id, label="B", field_type="text")
    f3 = await form_svc.add_field(db, form.id, label="C", field_type="text")

    # Reverse the order: C, B, A
    await form_svc.reorder_fields(db, form.id, [str(f3.id), str(f2.id), str(f1.id)])

    fetched = await form_svc.get_form(db, form.id)
    assert fetched is not None
    fields = sorted(fetched.fields, key=lambda f: f.position)
    assert fields[0].label == "C"
    assert fields[1].label == "B"
    assert fields[2].label == "A"


@pytest.mark.asyncio
async def test_create_submission(db: AsyncSession, location: Location):
    form = await form_svc.create_form(db, location.id, name="Submit Form")
    sub = await form_svc.create_submission(
        db, location.id, form.id,
        data_json={"name": "Alice", "email": "alice@test.com"},
        source_ip="127.0.0.1",
    )
    assert sub.data_json == {"name": "Alice", "email": "alice@test.com"}
    assert sub.source_ip == "127.0.0.1"
    assert sub.form_id == form.id


@pytest.mark.asyncio
async def test_list_submissions(db: AsyncSession, location: Location):
    form = await form_svc.create_form(db, location.id, name="List Sub Form")
    for i in range(3):
        await form_svc.create_submission(
            db, location.id, form.id, data_json={"index": i}
        )

    subs, total = await form_svc.list_submissions(db, form.id)
    assert total == 3
    assert len(subs) == 3


@pytest.mark.asyncio
async def test_delete_form_cascades_fields(db: AsyncSession, location: Location):
    form = await form_svc.create_form(db, location.id, name="Cascade Form")
    f1 = await form_svc.add_field(db, form.id, label="Field 1", field_type="text")
    f2 = await form_svc.add_field(db, form.id, label="Field 2", field_type="email")

    field_ids = [f1.id, f2.id]
    await form_svc.delete_form(db, form.id)

    # Verify fields are gone
    for fid in field_ids:
        stmt = select(FormField).where(FormField.id == fid)
        result = (await db.execute(stmt)).scalar_one_or_none()
        assert result is None
