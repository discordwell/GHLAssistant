"""Tests for browser-backed workflow rebuild/export."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from crm.models.base import Base
from crm.models.tag import Tag
from crm.models.ghl_raw import GHLRawEntity
from crm.models.location import Location
from crm.sync.export_workflows import build_workflow_rebuild_plan, export_workflows_via_browser


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
        ghl_location_id="loc_123",
    )
    db.add(loc)
    await db.commit()
    await db.refresh(loc)
    return loc


class FakeWorkflowsAPI:
    def __init__(self, items: list[dict] | None = None, details_by_id: dict[str, dict] | None = None):
        self.items = list(items or [])
        self.details_by_id = dict(details_by_id or {})

    async def list(self, location_id: str | None = None):
        return {"workflows": list(self.items)}

    async def get(self, workflow_id: str):
        return self.details_by_id.get(workflow_id, {"id": workflow_id})


class FakeGHL:
    def __init__(self, workflows: FakeWorkflowsAPI):
        self.workflows = workflows


@pytest.mark.asyncio
async def test_build_workflow_rebuild_plan_skips_existing_remote(db: AsyncSession, location: Location):
    db.add(
        GHLRawEntity(
            location_id=location.id,
            entity_type="workflow",
            ghl_id="wf_local_1",
            ghl_location_id=location.ghl_location_id,
            payload_json={"id": "wf_local_1", "name": "Alpha Workflow", "status": "draft"},
            source="api",
        )
    )
    db.add(
        GHLRawEntity(
            location_id=location.id,
            entity_type="workflow",
            ghl_id="wf_local_2",
            ghl_location_id=location.ghl_location_id,
            payload_json={"id": "wf_local_2", "name": "Beta Workflow", "status": "draft"},
            source="api",
        )
    )
    await db.commit()

    ghl = FakeGHL(
        workflows=FakeWorkflowsAPI(
            items=[{"id": "wf_remote_beta", "name": "Beta Workflow", "status": "draft"}],
            details_by_id={},
        )
    )

    plan = await build_workflow_rebuild_plan(db, location, ghl, tab_id=7, only_missing=True)
    assert plan["summary"]["workflows"] == 1
    assert plan["summary"]["skipped_existing"] == 1
    assert len(plan["items"]) == 1
    assert plan["items"][0]["name"] == "Alpha Workflow"
    assert plan["items"][0]["domain"] == "workflows"


@pytest.mark.asyncio
async def test_build_workflow_rebuild_plan_includes_fidelity2_action_steps_and_finalizes(db: AsyncSession, location: Location):
    db.add(
        GHLRawEntity(
            location_id=location.id,
            entity_type="workflow",
            ghl_id="wf_local_1",
            ghl_location_id=location.ghl_location_id,
            payload_json={
                "id": "wf_local_1",
                "name": "Alpha Workflow",
                "status": "draft",
                "actions": [
                    {"type": "send_sms", "message": "Hello"},
                    {"type": "wait", "minutes": 2},
                    {"type": "add_tag", "tagName": "New Lead"},
                    {"type": "send_email", "subject": "Welcome", "body": "Thanks"},
                ],
            },
            source="api",
        )
    )
    await db.commit()

    ghl = FakeGHL(workflows=FakeWorkflowsAPI(items=[], details_by_id={}))
    plan = await build_workflow_rebuild_plan(db, location, ghl, tab_id=7, only_missing=True, fidelity=2)

    assert plan["summary"]["workflows"] == 1
    item = plan["items"][0]
    assert item["meta"]["fidelity"] == 2

    parsed_kinds = [s["kind"] for s in item["meta"]["parsed_steps"]]
    assert "send_sms" in parsed_kinds
    assert "delay" in parsed_kinds
    assert "add_tag" in parsed_kinds
    assert "send_email" in parsed_kinds

    step_names = [s["name"] for s in item["steps"]]
    assert "wf_step_001_select_send_sms" in step_names
    assert "wf_step_002_select_wait" in step_names
    assert "wf_step_003_select_add_tag" in step_names
    assert "wf_step_004_select_send_email" in step_names

    # Final save/publish attempt should occur after we try to add actions.
    assert "find_save_workflow" in step_names
    assert step_names.index("wf_step_001_select_send_sms") < step_names.index("find_save_workflow")


@pytest.mark.asyncio
async def test_build_workflow_rebuild_plan_fidelity3_adds_trigger_config_steps(db: AsyncSession, location: Location):
    db.add(
        Tag(
            location_id=location.id,
            ghl_location_id=location.ghl_location_id,
            ghl_id="tag_1",
            name="New Lead",
        )
    )
    db.add(
        GHLRawEntity(
            location_id=location.id,
            entity_type="workflow",
            ghl_id="wf_local_1",
            ghl_location_id=location.ghl_location_id,
            payload_json={
                "id": "wf_local_1",
                "name": "Tagged Workflow",
                "status": "draft",
                "trigger": {"type": "tag_added", "tagId": "tag_1"},
            },
            source="api",
        )
    )
    await db.commit()

    ghl = FakeGHL(workflows=FakeWorkflowsAPI(items=[], details_by_id={}))
    plan = await build_workflow_rebuild_plan(db, location, ghl, tab_id=7, only_missing=True, fidelity=3)

    assert plan["summary"]["workflows"] == 1
    item = plan["items"][0]
    assert item["meta"]["fidelity"] == 3
    assert item["meta"]["trigger"] == "tag_added"
    assert item["meta"]["trigger_config"].get("tag") == "New Lead"

    step_names = [s["name"] for s in item["steps"]]
    assert "wf_trigger_set_tag" in step_names


@pytest.mark.asyncio
async def test_export_workflows_via_browser_execute_reconciles_raw(db: AsyncSession, location: Location, monkeypatch):
    db.add(
        GHLRawEntity(
            location_id=location.id,
            entity_type="workflow",
            ghl_id="wf_local_1",
            ghl_location_id=location.ghl_location_id,
            payload_json={"id": "wf_local_1", "name": "Alpha Workflow", "status": "draft"},
            source="api",
        )
    )
    await db.commit()

    workflows_api = FakeWorkflowsAPI(
        items=[],
        details_by_id={
            "wf_remote_alpha": {"id": "wf_remote_alpha", "name": "Alpha Workflow", "status": "draft"},
        },
    )
    ghl = FakeGHL(workflows=workflows_api)

    archived: list[str] = []

    def fake_archive(location_key: str, domain: str, payload):
        archived.append(domain)
        return Path(f"/tmp/{domain}.json")

    async def fake_execute(*args, **kwargs):
        # Simulate the workflow appearing in remote list after UI creation.
        workflows_api.items.append({"id": "wf_remote_alpha", "name": "Alpha Workflow", "status": "draft"})
        return {
            "success": True,
            "items_total": 1,
            "items_completed": 1,
            "errors": [],
        }

    monkeypatch.setattr("crm.sync.export_workflows.write_sync_archive", fake_archive)
    monkeypatch.setattr("crm.sync.export_workflows.execute_browser_export_plan", fake_execute)

    result = await export_workflows_via_browser(
        db,
        location,
        ghl,
        tab_id=1,
        execute=True,
        profile_name="ghl_session",
        headless=True,
        continue_on_error=True,
    )

    assert result.created == 1
    assert result.updated == 1  # stored raw payload for rebuilt workflow
    assert "workflows_browser_export_plan" in archived
    assert "workflows_browser_export_execution" in archived
    assert "workflows_browser_export_reconciliation" in archived

    rows = list((await db.execute(
        select(GHLRawEntity).where(
            GHLRawEntity.location_id == location.id,
            GHLRawEntity.entity_type == "workflow",
            GHLRawEntity.ghl_id == "wf_remote_alpha",
        )
    )).scalars().all())
    assert len(rows) == 1
    assert rows[0].payload_json.get("name") == "Alpha Workflow"
    assert isinstance(rows[0].payload_json.get("_maxlevel"), dict)
