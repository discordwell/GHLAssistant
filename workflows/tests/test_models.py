"""Tests for Workflow Builder database models."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from workflows.models.workflow import Workflow, WorkflowStep
from workflows.models.execution import WorkflowExecution, WorkflowStepExecution
from workflows.models.log import WorkflowLog


@pytest.mark.asyncio
async def test_create_workflow(db: AsyncSession):
    wf = Workflow(name="Test Workflow", description="A test", status="draft")
    db.add(wf)
    await db.commit()
    await db.refresh(wf)
    assert wf.id is not None
    assert wf.name == "Test Workflow"
    assert wf.status == "draft"


@pytest.mark.asyncio
async def test_workflow_default_status(db: AsyncSession):
    wf = Workflow(name="Default Status")
    db.add(wf)
    await db.commit()
    await db.refresh(wf)
    assert wf.status == "draft"


@pytest.mark.asyncio
async def test_create_step(db: AsyncSession):
    wf = Workflow(name="WF with Steps")
    db.add(wf)
    await db.commit()
    await db.refresh(wf)

    step = WorkflowStep(
        workflow_id=wf.id,
        step_type="action",
        action_type="send_email",
        label="Send Welcome Email",
        position=0,
    )
    db.add(step)
    await db.commit()
    await db.refresh(step)
    assert step.id is not None
    assert step.step_type == "action"
    assert step.action_type == "send_email"


@pytest.mark.asyncio
async def test_step_canvas_defaults(db: AsyncSession):
    wf = Workflow(name="Canvas WF")
    db.add(wf)
    await db.commit()

    step = WorkflowStep(workflow_id=wf.id, step_type="delay", position=0)
    db.add(step)
    await db.commit()
    await db.refresh(step)
    assert step.canvas_x == 300.0
    assert step.canvas_y == 100.0


@pytest.mark.asyncio
async def test_create_execution(db: AsyncSession):
    wf = Workflow(name="Exec WF")
    db.add(wf)
    await db.commit()

    ex = WorkflowExecution(workflow_id=wf.id, status="running")
    db.add(ex)
    await db.commit()
    await db.refresh(ex)
    assert ex.id is not None
    assert ex.status == "running"
    assert ex.steps_completed == 0


@pytest.mark.asyncio
async def test_create_step_execution(db: AsyncSession):
    wf = Workflow(name="Step Exec WF")
    db.add(wf)
    await db.commit()

    step = WorkflowStep(workflow_id=wf.id, step_type="action", position=0)
    db.add(step)
    await db.commit()

    ex = WorkflowExecution(workflow_id=wf.id, status="running")
    db.add(ex)
    await db.commit()

    step_ex = WorkflowStepExecution(
        execution_id=ex.id,
        step_id=step.id,
        status="completed",
        output_data={"result": "ok"},
        duration_ms=42,
    )
    db.add(step_ex)
    await db.commit()
    await db.refresh(step_ex)
    assert step_ex.status == "completed"
    assert step_ex.duration_ms == 42


@pytest.mark.asyncio
async def test_create_log(db: AsyncSession):
    wf = Workflow(name="Log WF")
    db.add(wf)
    await db.commit()

    log = WorkflowLog(
        workflow_id=wf.id,
        level="info",
        event="workflow.created",
        message="Workflow created",
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    assert log.event == "workflow.created"
    assert log.level == "info"


@pytest.mark.asyncio
async def test_workflow_cascade_delete(db: AsyncSession):
    wf = Workflow(name="Cascade WF")
    db.add(wf)
    await db.commit()

    step = WorkflowStep(workflow_id=wf.id, step_type="action", position=0)
    db.add(step)
    await db.commit()

    await db.delete(wf)
    await db.commit()

    # Step should be deleted via cascade
    from sqlalchemy import select
    result = await db.execute(select(WorkflowStep).where(WorkflowStep.id == step.id))
    assert result.scalar_one_or_none() is None
