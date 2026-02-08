"""Regression tests for notes/tasks sync mappings."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from crm.models.base import Base
from crm.models.contact import Contact
from crm.models.ghl_raw import GHLRawEntity
from crm.models.location import Location
from crm.models.note import Note
from crm.models.task import Task
from crm.sync.import_notes import import_notes
from crm.sync.import_tasks import import_tasks


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
async def test_import_notes_creates_and_updates(db: AsyncSession, location: Location):
    contact = Contact(location_id=location.id, ghl_id="ghl-c-1", first_name="Alice")
    db.add(contact)
    await db.commit()
    await db.refresh(contact)

    notes_by_contact = {
        "ghl-c-1": [{"id": "ghl-note-1", "body": "Hello", "createdBy": "tester"}],
    }
    result = await import_notes(db, location, notes_by_contact, contact_map={"ghl-c-1": contact.id})
    assert result.created == 1

    note = (
        await db.scalar(
            select(Note).where(Note.location_id == location.id, Note.ghl_id == "ghl-note-1")
        )
    )
    assert note is not None
    assert note.body == "Hello"
    assert note.contact_id == contact.id

    raw = (
        await db.scalar(
            select(GHLRawEntity).where(
                GHLRawEntity.location_id == location.id,
                GHLRawEntity.entity_type == "note",
                GHLRawEntity.ghl_id == "ghl-note-1",
            )
        )
    )
    assert raw is not None

    # Update same note id
    notes_by_contact = {
        "ghl-c-1": [{"id": "ghl-note-1", "body": "Hello again", "createdBy": "tester"}],
    }
    result = await import_notes(db, location, notes_by_contact, contact_map={"ghl-c-1": contact.id})
    assert result.updated == 1

    await db.refresh(note)
    assert note.body == "Hello again"


@pytest.mark.asyncio
async def test_import_tasks_creates_and_parses_due_date(db: AsyncSession, location: Location):
    contact = Contact(location_id=location.id, ghl_id="ghl-c-1", first_name="Alice")
    db.add(contact)
    await db.commit()
    await db.refresh(contact)

    tasks_by_contact = {
        "ghl-c-1": [
            {
                "id": "ghl-task-1",
                "title": "Call back",
                "description": "Follow up",
                "dueDate": "2026-02-08T10:00:00Z",
                "status": "open",
                "priority": 2,
                "assignedTo": "tester",
            }
        ]
    }
    result = await import_tasks(db, location, tasks_by_contact, contact_map={"ghl-c-1": contact.id})
    assert result.created == 1

    task = (
        await db.scalar(
            select(Task).where(Task.location_id == location.id, Task.ghl_id == "ghl-task-1")
        )
    )
    assert task is not None
    assert task.title == "Call back"
    assert task.description == "Follow up"
    assert task.due_date == date(2026, 2, 8)
    assert task.status == "open"
    assert task.priority == 2
    assert task.assigned_to == "tester"
    assert task.contact_id == contact.id

    raw = (
        await db.scalar(
            select(GHLRawEntity).where(
                GHLRawEntity.location_id == location.id,
                GHLRawEntity.entity_type == "task",
                GHLRawEntity.ghl_id == "ghl-task-1",
            )
        )
    )
    assert raw is not None


@pytest.mark.asyncio
async def test_import_tasks_allows_orphaned_contact(db: AsyncSession, location: Location):
    tasks_by_contact = {
        "ghl-missing-contact": [{"id": "ghl-task-orphan", "title": "Orphan Task"}],
    }
    result = await import_tasks(db, location, tasks_by_contact, contact_map={})
    assert result.created == 1

    task = (
        await db.scalar(
            select(Task).where(Task.location_id == location.id, Task.ghl_id == "ghl-task-orphan")
        )
    )
    assert task is not None
    assert task.contact_id is None

