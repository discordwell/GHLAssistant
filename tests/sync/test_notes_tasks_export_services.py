"""Unit tests for Notes/Tasks export using services-domain write endpoints."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from crm.models.base import Base
from crm.models.contact import Contact
from crm.models.location import Location
from crm.models.note import Note
from crm.models.task import Task
from crm.sync.exporter import export_notes, export_tasks


class _FakeConfig:
    def __init__(self, *, token_id: str | None):
        self.token_id = token_id


class FakeNotesService:
    def __init__(self):
        self.create_calls: list[dict] = []
        self.update_calls: list[dict] = []

    async def create(self, *, location_id: str, body: str, contact_id: str | None = None, relations=None):
        self.create_calls.append(
            {"location_id": location_id, "body": body, "contact_id": contact_id, "relations": relations}
        )
        return {"note": {"id": "ghl_note_created"}}

    async def update(self, note_id: str, *, location_id: str, body: str | None = None, relations=None):
        self.update_calls.append(
            {"note_id": note_id, "location_id": location_id, "body": body, "relations": relations}
        )
        return {"note": {"id": note_id}}


class FakeTasksService:
    def __init__(self):
        self.create_calls: list[dict] = []
        self.update_calls: list[dict] = []

    async def create(
        self,
        *,
        location_id: str,
        title: str,
        contact_id: str | None = None,
        due_date: str | None = None,
        description: str | None = None,
        status: str = "incomplete",
        assigned_to: str | None = None,
        relations=None,
        properties=None,
    ):
        self.create_calls.append(
            {
                "location_id": location_id,
                "title": title,
                "contact_id": contact_id,
                "due_date": due_date,
                "description": description,
                "status": status,
                "assigned_to": assigned_to,
                "relations": relations,
                "properties": properties,
            }
        )
        return {"record": {"id": "ghl_task_created"}}

    async def update(
        self,
        task_id: str,
        *,
        location_id: str,
        title: str | None = None,
        due_date: str | None = None,
        description: str | None = None,
        status: str | None = None,
        assigned_to: str | None = None,
        relations=None,
        properties=None,
    ):
        self.update_calls.append(
            {
                "task_id": task_id,
                "location_id": location_id,
                "title": title,
                "due_date": due_date,
                "description": description,
                "status": status,
                "assigned_to": assigned_to,
                "relations": relations,
                "properties": properties,
            }
        )
        return {"record": {"id": task_id}}


class FakeContactsAPI:
    def __init__(self):
        self.add_note_calls: list[tuple] = []
        self.add_task_calls: list[tuple] = []

    async def add_note(self, *args, **kwargs):
        self.add_note_calls.append((args, kwargs))
        return {"note": {"id": "fallback_note"}}

    async def add_task(self, *args, **kwargs):
        self.add_task_calls.append((args, kwargs))
        return {"task": {"id": "fallback_task"}}


class FakeGHL:
    def __init__(self, *, token_id: str | None = "tok"):
        self.config = _FakeConfig(token_id=token_id)
        self.notes_service = FakeNotesService()
        self.tasks_service = FakeTasksService()
        self.contacts = FakeContactsAPI()


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_export_notes_uses_services_create_and_update(db: AsyncSession):
    location = Location(
        id=uuid.uuid4(),
        name="Test Location",
        slug="test-location",
        timezone="UTC",
        ghl_location_id="ghl_loc_123",
    )
    db.add(location)
    await db.flush()

    contact = Contact(
        location_id=location.id,
        first_name="Test",
        ghl_id="ghl_contact_123",
    )
    db.add(contact)
    await db.flush()

    n1 = Note(location_id=location.id, contact_id=contact.id, body="new note")
    n2 = Note(
        location_id=location.id,
        contact_id=contact.id,
        body="updated note",
        ghl_id="ghl_note_existing",
        ghl_location_id=location.ghl_location_id,
        # Ensure exporter considers this row "dirty".
        last_synced_at=datetime(2000, 1, 1, tzinfo=timezone.utc),
    )
    db.add_all([n1, n2])
    await db.commit()

    ghl = FakeGHL(token_id="tok")
    result = await export_notes(db, location, ghl)

    assert result.created == 1
    assert result.updated == 1
    assert result.errors == []

    assert len(ghl.notes_service.create_calls) == 1
    assert len(ghl.notes_service.update_calls) == 1
    # Fallback endpoints should not be used when token-id is present.
    assert ghl.contacts.add_note_calls == []

    await db.refresh(n1)
    await db.refresh(n2)
    assert n1.ghl_id == "ghl_note_created"
    assert n2.last_synced_at is not None


@pytest.mark.asyncio
async def test_export_tasks_uses_services_create_and_update(db: AsyncSession):
    location = Location(
        id=uuid.uuid4(),
        name="Test Location",
        slug="test-location",
        timezone="UTC",
        ghl_location_id="ghl_loc_123",
    )
    db.add(location)
    await db.flush()

    contact = Contact(
        location_id=location.id,
        first_name="Test",
        ghl_id="ghl_contact_123",
    )
    db.add(contact)
    await db.flush()

    t1 = Task(
        location_id=location.id,
        title="new task",
        contact_id=contact.id,
        due_date=date(2026, 2, 11),
        status="done",
    )
    t2 = Task(
        location_id=location.id,
        title="updated task",
        contact_id=contact.id,
        due_date=date(2026, 2, 12),
        status="pending",
        ghl_id="ghl_task_existing",
        ghl_location_id=location.ghl_location_id,
        last_synced_at=datetime(2000, 1, 1, tzinfo=timezone.utc),
    )
    db.add_all([t1, t2])
    await db.commit()

    ghl = FakeGHL(token_id="tok")
    result = await export_tasks(db, location, ghl)

    assert result.created == 1
    assert result.updated == 1
    assert result.errors == []

    assert len(ghl.tasks_service.create_calls) == 1
    assert len(ghl.tasks_service.update_calls) == 1
    assert ghl.contacts.add_task_calls == []

    # Ensure local -> remote status mapping happened.
    assert ghl.tasks_service.create_calls[0]["status"] == "completed"
    assert ghl.tasks_service.update_calls[0]["status"] == "incomplete"

    await db.refresh(t1)
    await db.refresh(t2)
    assert t1.ghl_id == "ghl_task_created"
    assert t2.last_synced_at is not None

