"""Trigger service — detects and fires workflow triggers."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.workflow import Workflow

logger = logging.getLogger(__name__)

# Trigger type → handler mapping
TRIGGER_TYPES = {
    "manual",
    "webhook",
    "contact_created",
    "tag_added",
    "tag_removed",
    "opportunity_stage_changed",
    "form_submitted",
    "time_based",
}


async def fire_trigger(
    db: AsyncSession,
    trigger_type: str,
    trigger_data: dict,
    location_id: str | None = None,
) -> list[dict]:
    """Find all published workflows matching a trigger and execute them.

    Returns a list of execution results.
    """
    from ..engine.runner import WorkflowRunner

    # Find matching workflows
    stmt = (
        select(Workflow)
        .where(Workflow.status == "published")
        .where(Workflow.trigger_type == trigger_type)
    )
    if location_id:
        stmt = stmt.where(Workflow.ghl_location_id == location_id)

    result = await db.execute(stmt)
    workflows = list(result.scalars().all())

    if not workflows:
        return []

    results = []
    runner = WorkflowRunner(db)

    for wf in workflows:
        # Check trigger config match (if any)
        if not _matches_trigger_config(wf.trigger_config, trigger_data):
            continue

        try:
            execution = await runner.run(wf.id, trigger_data=trigger_data)
            results.append({
                "workflow_id": str(wf.id),
                "workflow_name": wf.name,
                "execution_id": str(execution.id),
                "status": execution.status,
                "steps_completed": execution.steps_completed,
            })
        except Exception as e:
            logger.error(f"Failed to run workflow {wf.name}: {e}")
            results.append({
                "workflow_id": str(wf.id),
                "workflow_name": wf.name,
                "error": str(e),
            })

    return results


def _matches_trigger_config(config: dict | None, data: dict) -> bool:
    """Check if trigger data matches the workflow's trigger configuration.

    A None/empty config matches anything.
    Otherwise, all keys in config must match corresponding keys in data.
    """
    if not config:
        return True

    filters = config.get("filters", {})
    for key, expected in filters.items():
        actual = data.get(key)
        if isinstance(expected, list):
            if actual not in expected:
                return False
        elif actual != expected:
            return False

    return True


async def process_ghl_event(
    db: AsyncSession,
    event_type: str,
    payload: dict,
) -> list[dict]:
    """Process a GoHighLevel webhook event and fire matching triggers.

    Maps GHL event types to internal trigger types.
    """
    # Map GHL event types to internal trigger types
    event_map = {
        "ContactCreate": "contact_created",
        "ContactTagUpdate": "tag_added",
        "OpportunityStageUpdate": "opportunity_stage_changed",
        "FormSubmission": "form_submitted",
    }

    trigger_type = event_map.get(event_type)
    if not trigger_type:
        return []

    location_id = payload.get("locationId") or payload.get("location_id")
    return await fire_trigger(db, trigger_type, payload, location_id=location_id)
