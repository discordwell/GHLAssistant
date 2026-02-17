"""Tests for webhook receiver and trigger service."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from workflows.services import workflow_svc, step_svc
from workflows.services.trigger_svc import (
    fire_trigger,
    process_ghl_event,
    _matches_trigger_config,
    TRIGGER_TYPES,
)


class TestWebhookEndpoint:
    @pytest.mark.asyncio
    async def test_webhook_triggers_published_workflow(
        self, client: AsyncClient, db: AsyncSession
    ):
        wf = await workflow_svc.create_workflow(
            db, name="Webhook WF", trigger_type="webhook"
        )
        await workflow_svc.publish_workflow(db, wf.id)
        await step_svc.create_step(db, wf.id, step_type="delay", config={"seconds": 0})

        resp = await client.post(
            f"/webhooks/{wf.id}",
            json={"contact_id": "c123", "name": "Test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["mode"] == "queued"
        assert data["dispatch_status"] in {"pending", "running", "completed"}
        assert "dispatch_id" in data

    @pytest.mark.asyncio
    async def test_webhook_rejects_unpublished(
        self, client: AsyncClient, db: AsyncSession
    ):
        wf = await workflow_svc.create_workflow(db, name="Draft WF")

        resp = await client.post(
            f"/webhooks/{wf.id}",
            json={"test": True},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_webhook_not_found(self, client: AsyncClient):
        fake_id = uuid.uuid4()
        resp = await client.post(
            f"/webhooks/{fake_id}",
            json={"test": True},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_webhook_test_page(
        self, client: AsyncClient, db: AsyncSession
    ):
        wf = await workflow_svc.create_workflow(db, name="Test Info WF")

        resp = await client.get(f"/webhooks/{wf.id}/test")
        assert resp.status_code == 200
        data = resp.json()
        assert "webhook_url" in data
        assert data["workflow"]["name"] == "Test Info WF"

    @pytest.mark.asyncio
    async def test_dispatch_status_not_found(self, client: AsyncClient):
        resp = await client.get(f"/webhooks/dispatches/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestTriggerConfig:
    def test_empty_config_matches_all(self):
        assert _matches_trigger_config(None, {"any": "data"}) is True
        assert _matches_trigger_config({}, {"any": "data"}) is True

    def test_filter_match(self):
        config = {"filters": {"tag": "VIP"}}
        assert _matches_trigger_config(config, {"tag": "VIP"}) is True
        assert _matches_trigger_config(config, {"tag": "Basic"}) is False

    def test_filter_list_match(self):
        config = {"filters": {"status": ["active", "pending"]}}
        assert _matches_trigger_config(config, {"status": "active"}) is True
        assert _matches_trigger_config(config, {"status": "closed"}) is False


class TestFireTrigger:
    @pytest.mark.asyncio
    async def test_fire_trigger_no_matching_workflows(self, db: AsyncSession):
        results = await fire_trigger(db, "contact_created", {"name": "John"})
        assert results == []

    @pytest.mark.asyncio
    async def test_fire_trigger_matches_published(self, db: AsyncSession):
        wf = await workflow_svc.create_workflow(
            db, name="On Contact", trigger_type="contact_created"
        )
        await workflow_svc.publish_workflow(db, wf.id)
        await step_svc.create_step(db, wf.id, step_type="delay", config={"seconds": 0})

        results = await fire_trigger(db, "contact_created", {"name": "John"})
        assert len(results) == 1
        assert results[0]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_fire_trigger_skips_draft(self, db: AsyncSession):
        await workflow_svc.create_workflow(
            db, name="Draft Trigger", trigger_type="contact_created"
        )
        results = await fire_trigger(db, "contact_created", {"name": "John"})
        assert results == []

    @pytest.mark.asyncio
    async def test_fire_trigger_filters_by_location(self, db: AsyncSession):
        wf = await workflow_svc.create_workflow(
            db, name="Location WF", trigger_type="tag_added"
        )
        await workflow_svc.publish_workflow(db, wf.id)
        # Update location_id
        wf.ghl_location_id = "loc123"
        await db.commit()
        await step_svc.create_step(db, wf.id, step_type="delay", config={"seconds": 0})

        # Wrong location
        results = await fire_trigger(
            db, "tag_added", {"tag": "VIP"}, location_id="loc999"
        )
        assert results == []

        # Correct location
        results = await fire_trigger(
            db, "tag_added", {"tag": "VIP"}, location_id="loc123"
        )
        assert len(results) == 1


class TestProcessGHLEvent:
    @pytest.mark.asyncio
    async def test_maps_contact_create(self, db: AsyncSession):
        wf = await workflow_svc.create_workflow(
            db, name="GHL Contact", trigger_type="contact_created"
        )
        await workflow_svc.publish_workflow(db, wf.id)
        await step_svc.create_step(db, wf.id, step_type="delay", config={"seconds": 0})

        results = await process_ghl_event(
            db, "ContactCreate", {"name": "Jane", "locationId": None}
        )
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_unknown_event_type(self, db: AsyncSession):
        results = await process_ghl_event(db, "UnknownEvent", {})
        assert results == []


class TestTriggerTypes:
    def test_expected_types_exist(self):
        assert "manual" in TRIGGER_TYPES
        assert "webhook" in TRIGGER_TYPES
        assert "contact_created" in TRIGGER_TYPES
        assert "tag_added" in TRIGGER_TYPES
        assert "opportunity_stage_changed" in TRIGGER_TYPES
