"""Workflow execution runner."""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.workflow import Workflow, WorkflowStep
from ..models.execution import WorkflowExecution, WorkflowStepExecution
from ..models.log import WorkflowLog
from .context import ExecutionContext
from .evaluator import evaluate_condition


class WorkflowRunner:
    """Executes a workflow by traversing its step graph."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def run(
        self,
        workflow_id: uuid.UUID,
        trigger_data: dict | None = None,
    ) -> WorkflowExecution:
        """Execute a workflow from start to finish."""
        # Load workflow with steps
        stmt = select(Workflow).where(Workflow.id == workflow_id)
        result = await self.db.execute(stmt)
        workflow = result.scalar_one_or_none()
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")

        # Create execution record
        execution = WorkflowExecution(
            workflow_id=workflow_id,
            status="running",
            trigger_data=trigger_data,
        )
        self.db.add(execution)
        await self.db.commit()
        await self.db.refresh(execution)

        # Log start
        await self._log(workflow_id, execution.id, "info", "execution.started", "Workflow execution started")

        # Build context
        ctx = ExecutionContext(trigger_data)

        # Load steps
        steps_stmt = (
            select(WorkflowStep)
            .where(WorkflowStep.workflow_id == workflow_id)
            .order_by(WorkflowStep.position)
        )
        steps_result = await self.db.execute(steps_stmt)
        steps = list(steps_result.scalars().all())

        if not steps:
            execution.status = "completed"
            execution.completed_at = datetime.now(timezone.utc)
            await self.db.commit()
            return execution

        # Build step lookup
        step_map = {step.id: step for step in steps}

        # Start from first step (lowest position)
        current_step = steps[0]

        try:
            visited: set[uuid.UUID] = set()
            while current_step:
                if current_step.id in visited:
                    raise RuntimeError(f"Cycle detected at step {current_step.id}")
                visited.add(current_step.id)
                step_result = await self._execute_step(execution, current_step, ctx)

                execution.steps_completed += 1
                await self.db.commit()

                # Determine next step
                if current_step.step_type == "condition":
                    # Branch based on condition result
                    branch_result = step_result.get("branch", True)
                    next_id = (
                        current_step.true_branch_step_id if branch_result
                        else current_step.false_branch_step_id
                    )
                else:
                    next_id = current_step.next_step_id

                current_step = step_map.get(next_id) if next_id else None

            # Completed successfully
            execution.status = "completed"
            execution.completed_at = datetime.now(timezone.utc)
            execution.context_data = ctx.to_dict()
            await self.db.commit()
            await self._log(workflow_id, execution.id, "info", "execution.completed",
                          f"Completed {execution.steps_completed} steps")

        except Exception as e:
            execution.status = "failed"
            execution.error_message = str(e)
            execution.completed_at = datetime.now(timezone.utc)
            await self.db.commit()
            await self._log(workflow_id, execution.id, "error", "execution.failed", str(e))

        await self.db.refresh(execution)
        return execution

    async def _execute_step(
        self,
        execution: WorkflowExecution,
        step: WorkflowStep,
        ctx: ExecutionContext,
    ) -> dict:
        """Execute a single step and return its output."""
        # Create step execution record
        step_ex = WorkflowStepExecution(
            execution_id=execution.id,
            step_id=step.id,
            status="running",
            input_data=step.config,
        )
        self.db.add(step_ex)
        await self.db.commit()

        start_time = time.monotonic()

        try:
            if step.step_type == "condition":
                result = self._evaluate_condition(step, ctx)
            elif step.step_type == "delay":
                result = await self._execute_delay(step, ctx)
            else:
                result = await self._execute_action(step, ctx)

            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            step_ex.status = "completed"
            step_ex.output_data = result
            step_ex.duration_ms = elapsed_ms
            await self.db.commit()

            # Store output in context
            ctx.set_step_output(str(step.id), result)

            return result

        except Exception as e:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            step_ex.status = "failed"
            step_ex.error_message = str(e)
            step_ex.duration_ms = elapsed_ms
            await self.db.commit()
            raise

    def _evaluate_condition(self, step: WorkflowStep, ctx: ExecutionContext) -> dict:
        """Evaluate a condition step."""
        config = ctx.resolve_config(step.config or {})
        result = evaluate_condition(config, ctx)
        return {"branch": result, "condition": config}

    async def _execute_delay(self, step: WorkflowStep, ctx: ExecutionContext) -> dict:
        """Execute a delay step."""
        config = step.config or {}
        seconds = config.get("seconds", 0)
        minutes = config.get("minutes", 0)
        hours = config.get("hours", 0)
        total_seconds = seconds + (minutes * 60) + (hours * 3600)

        if total_seconds > 0:
            # Cap at 5 minutes for safety in local execution
            total_seconds = min(total_seconds, 300)
            await asyncio.sleep(total_seconds)

        return {"waited_seconds": total_seconds}

    async def _execute_action(self, step: WorkflowStep, ctx: ExecutionContext) -> dict:
        """Execute an action step using GHL API."""
        config = ctx.resolve_config(step.config or {})
        action_type = step.action_type

        if not action_type:
            return {"skipped": True, "reason": "no action_type"}

        # Lazy import to avoid circular deps
        from .actions import execute_action
        return await execute_action(action_type, config, ctx)

    async def _log(
        self,
        workflow_id: uuid.UUID,
        execution_id: uuid.UUID,
        level: str,
        event: str,
        message: str,
    ) -> None:
        log = WorkflowLog(
            workflow_id=workflow_id,
            execution_id=execution_id,
            level=level,
            event=event,
            message=message,
        )
        self.db.add(log)
        await self.db.commit()
