"""Tests for the JSON API (step and connection CRUD)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from workflows.services import workflow_svc


@pytest.mark.asyncio
async def test_list_steps_empty(client: AsyncClient, db: AsyncSession):
    wf = await workflow_svc.create_workflow(db, name="API Test")
    res = await client.get(f"/api/workflows/{wf.id}/steps")
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_create_step_via_api(client: AsyncClient, db: AsyncSession):
    wf = await workflow_svc.create_workflow(db, name="API Create")
    res = await client.post(
        f"/api/workflows/{wf.id}/steps",
        json={"step_type": "action", "action_type": "send_email", "label": "Send"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["step_type"] == "action"
    assert data["action_type"] == "send_email"
    assert data["label"] == "Send"


@pytest.mark.asyncio
async def test_update_step_via_api(client: AsyncClient, db: AsyncSession):
    wf = await workflow_svc.create_workflow(db, name="API Update")
    create_res = await client.post(
        f"/api/workflows/{wf.id}/steps",
        json={"step_type": "action", "label": "Before"},
    )
    step_id = create_res.json()["id"]
    res = await client.patch(f"/api/steps/{step_id}", json={"label": "After"})
    assert res.status_code == 200
    assert res.json()["label"] == "After"


@pytest.mark.asyncio
async def test_delete_step_via_api(client: AsyncClient, db: AsyncSession):
    wf = await workflow_svc.create_workflow(db, name="API Delete")
    create_res = await client.post(
        f"/api/workflows/{wf.id}/steps",
        json={"step_type": "action"},
    )
    step_id = create_res.json()["id"]
    res = await client.delete(f"/api/steps/{step_id}")
    assert res.status_code == 200
    assert res.json()["deleted"] is True


@pytest.mark.asyncio
async def test_create_connection_via_api(client: AsyncClient, db: AsyncSession):
    wf = await workflow_svc.create_workflow(db, name="API Connect")
    r1 = await client.post(f"/api/workflows/{wf.id}/steps", json={"step_type": "action"})
    r2 = await client.post(f"/api/workflows/{wf.id}/steps", json={"step_type": "action"})
    res = await client.post("/api/connections", json={
        "from_step_id": r1.json()["id"],
        "to_step_id": r2.json()["id"],
        "connection_type": "next",
    })
    assert res.status_code == 200
    assert res.json()["connected"] is True


@pytest.mark.asyncio
async def test_dashboard_page(client: AsyncClient):
    res = await client.get("/")
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_new_workflow_form(client: AsyncClient):
    res = await client.get("/workflows/new")
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_create_workflow_form(client: AsyncClient):
    res = await client.post(
        "/workflows/new",
        data={"name": "Form WF", "description": "via form", "trigger_type": "manual"},
        follow_redirects=False,
    )
    assert res.status_code == 303
    assert "/edit" in res.headers["location"]


@pytest.mark.asyncio
async def test_executions_page(client: AsyncClient):
    res = await client.get("/executions/", follow_redirects=True)
    assert res.status_code == 200
