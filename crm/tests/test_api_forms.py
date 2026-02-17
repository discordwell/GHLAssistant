"""Test form API routes."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from crm.config import settings
from crm.models.form import Form, FormField, FormSubmission
from crm.models.location import Location


@pytest.mark.asyncio
async def test_forms_list_page(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/forms/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_forms_new_page(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/forms/new")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_forms_create(client: AsyncClient, location: Location):
    response = await client.post(
        f"/loc/{location.slug}/forms/",
        data={"name": "Contact Form"},
        follow_redirects=False,
    )
    assert response.status_code == 303


@pytest.mark.asyncio
async def test_forms_detail(
    client: AsyncClient, db: AsyncSession, location: Location
):
    form = Form(
        location_id=location.id,
        name="Detail Form",
    )
    db.add(form)
    await db.commit()
    await db.refresh(form)

    response = await client.get(f"/loc/{location.slug}/forms/{form.id}")
    assert response.status_code == 200
    assert "Detail Form" in response.text


@pytest.mark.asyncio
async def test_forms_add_field(
    client: AsyncClient, db: AsyncSession, location: Location
):
    form = Form(
        location_id=location.id,
        name="Field Form",
    )
    db.add(form)
    await db.commit()
    await db.refresh(form)

    response = await client.post(
        f"/loc/{location.slug}/forms/{form.id}/fields",
        data={"label": "Name", "field_type": "text"},
        follow_redirects=False,
    )
    assert response.status_code == 303


@pytest.mark.asyncio
async def test_forms_delete_field(
    client: AsyncClient, db: AsyncSession, location: Location
):
    form = Form(
        location_id=location.id,
        name="Del Field Form",
    )
    db.add(form)
    await db.commit()
    await db.refresh(form)

    field = FormField(
        form_id=form.id,
        label="To Delete",
        field_type="text",
        position=0,
    )
    db.add(field)
    await db.commit()
    await db.refresh(field)

    response = await client.post(
        f"/loc/{location.slug}/forms/{form.id}/fields/{field.id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 303


@pytest.mark.asyncio
async def test_forms_delete(
    client: AsyncClient, db: AsyncSession, location: Location
):
    form = Form(
        location_id=location.id,
        name="To Delete Form",
    )
    db.add(form)
    await db.commit()
    await db.refresh(form)

    response = await client.post(
        f"/loc/{location.slug}/forms/{form.id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 303


@pytest.mark.asyncio
async def test_forms_public_get(
    client: AsyncClient, db: AsyncSession, location: Location
):
    form = Form(
        location_id=location.id,
        name="Public Test Form",
        is_active=True,
    )
    db.add(form)
    await db.commit()
    await db.refresh(form)

    response = await client.get(f"/f/{form.id}")
    assert response.status_code == 200
    assert "Public Test Form" in response.text


@pytest.mark.asyncio
async def test_forms_public_submit(
    client: AsyncClient, db: AsyncSession, location: Location
):
    form = Form(
        location_id=location.id,
        name="Submit Form",
        is_active=True,
    )
    db.add(form)
    await db.commit()
    await db.refresh(form)

    field = FormField(
        form_id=form.id,
        label="Full Name",
        field_type="text",
        position=0,
    )
    db.add(field)
    await db.commit()
    await db.refresh(field)

    response = await client.post(
        f"/f/{form.id}",
        data={str(field.id): "John Doe"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_forms_list_empty(client: AsyncClient, location: Location):
    response = await client.get(f"/loc/{location.slug}/forms/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_forms_public_submit_honeypot_ignored(
    client: AsyncClient,
    db: AsyncSession,
    location: Location,
):
    form = Form(location_id=location.id, name="Honeypot Form", is_active=True)
    db.add(form)
    await db.commit()
    await db.refresh(form)

    field = FormField(form_id=form.id, label="Email", field_type="email", position=0)
    db.add(field)
    await db.commit()
    await db.refresh(field)

    response = await client.post(
        f"/f/{form.id}",
        data={
            str(field.id): "bot@example.com",
            settings.form_honeypot_field: "I am a bot",
        },
    )
    assert response.status_code == 200

    count = await db.scalar(
        select(func.count()).select_from(FormSubmission).where(FormSubmission.form_id == form.id)
    )
    assert count == 0


@pytest.mark.asyncio
async def test_forms_public_submit_rate_limited(
    client: AsyncClient,
    db: AsyncSession,
    location: Location,
    monkeypatch: pytest.MonkeyPatch,
):
    form = Form(location_id=location.id, name="Rate Limit Form", is_active=True)
    db.add(form)
    await db.commit()
    await db.refresh(form)

    field = FormField(form_id=form.id, label="Name", field_type="text", position=0)
    db.add(field)
    await db.commit()
    await db.refresh(field)

    monkeypatch.setattr(settings, "form_rate_limit_max_submissions", 1)
    monkeypatch.setattr(settings, "form_rate_limit_window_seconds", 60)
    monkeypatch.setattr(settings, "form_rate_limit_block_seconds", 60)

    first = await client.post(f"/f/{form.id}", data={str(field.id): "First"})
    second = await client.post(f"/f/{form.id}", data={str(field.id): "Second"})
    assert first.status_code == 200
    assert second.status_code == 429
