"""Tests for step management service."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from workflows.services import workflow_svc, step_svc


@pytest.mark.asyncio
async def test_create_step(db: AsyncSession):
    wf = await workflow_svc.create_workflow(db, name="Step WF")
    step = await step_svc.create_step(
        db, workflow_id=wf.id, step_type="action", action_type="send_email"
    )
    assert step.step_type == "action"
    assert step.action_type == "send_email"
    assert step.position == 0


@pytest.mark.asyncio
async def test_auto_position(db: AsyncSession):
    wf = await workflow_svc.create_workflow(db, name="Auto Pos")
    s1 = await step_svc.create_step(db, wf.id, step_type="action")
    s2 = await step_svc.create_step(db, wf.id, step_type="action")
    assert s1.position == 0
    assert s2.position == 1


@pytest.mark.asyncio
async def test_list_steps(db: AsyncSession):
    wf = await workflow_svc.create_workflow(db, name="List Steps")
    await step_svc.create_step(db, wf.id, step_type="action", label="A")
    await step_svc.create_step(db, wf.id, step_type="action", label="B")
    steps = await step_svc.list_steps(db, wf.id)
    assert len(steps) == 2


@pytest.mark.asyncio
async def test_update_step(db: AsyncSession):
    wf = await workflow_svc.create_workflow(db, name="Update Step")
    step = await step_svc.create_step(db, wf.id, step_type="action", label="Before")
    updated = await step_svc.update_step(db, step.id, label="After")
    assert updated.label == "After"


@pytest.mark.asyncio
async def test_delete_step(db: AsyncSession):
    wf = await workflow_svc.create_workflow(db, name="Del Step")
    step = await step_svc.create_step(db, wf.id, step_type="action")
    assert await step_svc.delete_step(db, step.id) is True
    assert await step_svc.get_step(db, step.id) is None


@pytest.mark.asyncio
async def test_connect_steps(db: AsyncSession):
    wf = await workflow_svc.create_workflow(db, name="Connect")
    s1 = await step_svc.create_step(db, wf.id, step_type="action")
    s2 = await step_svc.create_step(db, wf.id, step_type="action")
    connected = await step_svc.connect_steps(db, s1.id, s2.id, "next")
    assert connected.next_step_id == s2.id


@pytest.mark.asyncio
async def test_connect_true_branch(db: AsyncSession):
    wf = await workflow_svc.create_workflow(db, name="Branch")
    cond = await step_svc.create_step(db, wf.id, step_type="condition")
    s_true = await step_svc.create_step(db, wf.id, step_type="action")
    connected = await step_svc.connect_steps(db, cond.id, s_true.id, "true_branch")
    assert connected.true_branch_step_id == s_true.id


@pytest.mark.asyncio
async def test_disconnect_steps(db: AsyncSession):
    wf = await workflow_svc.create_workflow(db, name="Disconnect")
    s1 = await step_svc.create_step(db, wf.id, step_type="action")
    s2 = await step_svc.create_step(db, wf.id, step_type="action")
    await step_svc.connect_steps(db, s1.id, s2.id, "next")
    disconnected = await step_svc.disconnect_steps(db, s1.id, "next")
    assert disconnected.next_step_id is None


@pytest.mark.asyncio
async def test_default_label(db: AsyncSession):
    wf = await workflow_svc.create_workflow(db, name="Labels")
    s1 = await step_svc.create_step(db, wf.id, step_type="condition")
    s2 = await step_svc.create_step(db, wf.id, step_type="delay")
    s3 = await step_svc.create_step(db, wf.id, step_type="action", action_type="send_sms")
    assert s1.label == "If/Else"
    assert s2.label == "Wait"
    assert s3.label == "Send Sms"
