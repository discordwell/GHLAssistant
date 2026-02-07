"""Tests for workflow CRUD service."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from workflows.services import workflow_svc


@pytest.mark.asyncio
async def test_create_workflow(db: AsyncSession):
    wf = await workflow_svc.create_workflow(db, name="Test WF", description="desc")
    assert wf.name == "Test WF"
    assert wf.description == "desc"
    assert wf.status == "draft"


@pytest.mark.asyncio
async def test_list_workflows(db: AsyncSession):
    await workflow_svc.create_workflow(db, name="WF A")
    await workflow_svc.create_workflow(db, name="WF B")
    workflows = await workflow_svc.list_workflows(db)
    names = [w.name for w in workflows]
    assert "WF A" in names
    assert "WF B" in names


@pytest.mark.asyncio
async def test_get_workflow(db: AsyncSession):
    wf = await workflow_svc.create_workflow(db, name="Get Me")
    fetched = await workflow_svc.get_workflow(db, wf.id)
    assert fetched is not None
    assert fetched.name == "Get Me"


@pytest.mark.asyncio
async def test_get_workflow_not_found(db: AsyncSession):
    import uuid
    result = await workflow_svc.get_workflow(db, uuid.uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_update_workflow(db: AsyncSession):
    wf = await workflow_svc.create_workflow(db, name="Before")
    updated = await workflow_svc.update_workflow(db, wf.id, name="After")
    assert updated.name == "After"


@pytest.mark.asyncio
async def test_delete_workflow(db: AsyncSession):
    wf = await workflow_svc.create_workflow(db, name="Delete Me")
    assert await workflow_svc.delete_workflow(db, wf.id) is True
    assert await workflow_svc.get_workflow(db, wf.id) is None


@pytest.mark.asyncio
async def test_delete_workflow_not_found(db: AsyncSession):
    import uuid
    assert await workflow_svc.delete_workflow(db, uuid.uuid4()) is False


@pytest.mark.asyncio
async def test_publish_workflow(db: AsyncSession):
    wf = await workflow_svc.create_workflow(db, name="Publish Me")
    assert wf.status == "draft"
    published = await workflow_svc.publish_workflow(db, wf.id)
    assert published.status == "published"


@pytest.mark.asyncio
async def test_pause_workflow(db: AsyncSession):
    wf = await workflow_svc.create_workflow(db, name="Pause Me")
    await workflow_svc.publish_workflow(db, wf.id)
    paused = await workflow_svc.pause_workflow(db, wf.id)
    assert paused.status == "paused"


@pytest.mark.asyncio
async def test_create_with_trigger(db: AsyncSession):
    wf = await workflow_svc.create_workflow(
        db,
        name="Triggered",
        trigger_type="contact_created",
        trigger_config={"filter": "new_leads"},
    )
    assert wf.trigger_type == "contact_created"
    assert wf.trigger_config == {"filter": "new_leads"}
