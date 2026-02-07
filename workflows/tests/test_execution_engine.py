"""Tests for the workflow execution engine."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from workflows.engine.runner import WorkflowRunner
from workflows.services import workflow_svc, step_svc


@pytest.mark.asyncio
async def test_run_empty_workflow(db: AsyncSession):
    wf = await workflow_svc.create_workflow(db, name="Empty")
    runner = WorkflowRunner(db)
    execution = await runner.run(wf.id)
    assert execution.status == "completed"
    assert execution.steps_completed == 0


@pytest.mark.asyncio
async def test_run_single_delay_step(db: AsyncSession):
    wf = await workflow_svc.create_workflow(db, name="Delay WF")
    await step_svc.create_step(
        db, wf.id, step_type="delay", config={"seconds": 0}
    )
    runner = WorkflowRunner(db)
    execution = await runner.run(wf.id)
    assert execution.status == "completed"
    assert execution.steps_completed == 1


@pytest.mark.asyncio
async def test_run_condition_true_branch(db: AsyncSession):
    wf = await workflow_svc.create_workflow(db, name="Condition WF")
    cond = await step_svc.create_step(
        db, wf.id,
        step_type="condition",
        config={"field": "trigger.active", "operator": "equals", "value": True},
    )
    true_step = await step_svc.create_step(
        db, wf.id, step_type="delay", config={"seconds": 0}, label="True Path"
    )
    false_step = await step_svc.create_step(
        db, wf.id, step_type="delay", config={"seconds": 0}, label="False Path"
    )
    await step_svc.connect_steps(db, cond.id, true_step.id, "true_branch")
    await step_svc.connect_steps(db, cond.id, false_step.id, "false_branch")

    runner = WorkflowRunner(db)
    execution = await runner.run(wf.id, trigger_data={"active": True})
    assert execution.status == "completed"
    assert execution.steps_completed == 2  # condition + true_step


@pytest.mark.asyncio
async def test_run_condition_false_branch(db: AsyncSession):
    wf = await workflow_svc.create_workflow(db, name="False Branch WF")
    cond = await step_svc.create_step(
        db, wf.id,
        step_type="condition",
        config={"field": "trigger.active", "operator": "equals", "value": True},
    )
    true_step = await step_svc.create_step(
        db, wf.id, step_type="delay", config={"seconds": 0}, label="True"
    )
    false_step = await step_svc.create_step(
        db, wf.id, step_type="delay", config={"seconds": 0}, label="False"
    )
    await step_svc.connect_steps(db, cond.id, true_step.id, "true_branch")
    await step_svc.connect_steps(db, cond.id, false_step.id, "false_branch")

    runner = WorkflowRunner(db)
    execution = await runner.run(wf.id, trigger_data={"active": False})
    assert execution.status == "completed"
    assert execution.steps_completed == 2  # condition + false_step


@pytest.mark.asyncio
async def test_run_chained_steps(db: AsyncSession):
    wf = await workflow_svc.create_workflow(db, name="Chain WF")
    s1 = await step_svc.create_step(db, wf.id, step_type="delay", config={"seconds": 0})
    s2 = await step_svc.create_step(db, wf.id, step_type="delay", config={"seconds": 0})
    s3 = await step_svc.create_step(db, wf.id, step_type="delay", config={"seconds": 0})
    await step_svc.connect_steps(db, s1.id, s2.id, "next")
    await step_svc.connect_steps(db, s2.id, s3.id, "next")

    runner = WorkflowRunner(db)
    execution = await runner.run(wf.id)
    assert execution.status == "completed"
    assert execution.steps_completed == 3


@pytest.mark.asyncio
async def test_execution_records_step_results(db: AsyncSession):
    wf = await workflow_svc.create_workflow(db, name="Records WF")
    await step_svc.create_step(db, wf.id, step_type="delay", config={"seconds": 0})

    runner = WorkflowRunner(db)
    execution = await runner.run(wf.id)

    # Reload with step executions
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from workflows.models.execution import WorkflowExecution
    stmt = (
        select(WorkflowExecution)
        .where(WorkflowExecution.id == execution.id)
        .options(selectinload(WorkflowExecution.step_executions))
    )
    result = await db.execute(stmt)
    ex = result.scalar_one()
    assert len(ex.step_executions) == 1
    assert ex.step_executions[0].status == "completed"
    assert ex.step_executions[0].duration_ms is not None
