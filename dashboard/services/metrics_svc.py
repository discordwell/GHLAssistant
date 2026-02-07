"""Aggregate metrics from all 3 app databases."""

from __future__ import annotations

from sqlalchemy import text

from ..database import MultiDB
from .. import database as _db_module


async def get_metrics(db: MultiDB | None = None) -> dict[str, int]:
    """Query each database for counts, returning a flat dict of metric name -> value.

    If a database is missing or empty, returns 0 for that app's metrics.
    """
    db = db or _db_module.multi_db
    metrics: dict[str, int] = {}

    # CRM metrics
    try:
        async with db.crm_session() as session:
            for table, key in [
                ("contact", "crm_contacts"),
                ("opportunity", "crm_opportunities"),
                ("pipeline", "crm_pipelines"),
            ]:
                result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                metrics[key] = result.scalar() or 0
    except Exception:
        metrics.update(crm_contacts=0, crm_opportunities=0, crm_pipelines=0)

    # Hiring metrics
    try:
        with db.hiring_connection() as conn:
            for table, key in [
                ("candidate", "hiring_candidates"),
                ("position", "hiring_positions"),
            ]:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                metrics[key] = result.scalar() or 0
            result = conn.execute(
                text("SELECT COUNT(*) FROM candidate WHERE status = 'hired'")
            )
            metrics["hiring_hired"] = result.scalar() or 0
    except Exception:
        metrics.update(hiring_candidates=0, hiring_positions=0, hiring_hired=0)

    # Workflow metrics
    try:
        async with db.wf_session() as session:
            for table, key in [
                ("workflow", "wf_workflows"),
                ("workflow_execution", "wf_executions"),
            ]:
                result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                metrics[key] = result.scalar() or 0
            result = await session.execute(
                text("SELECT COUNT(*) FROM workflow_execution WHERE status = 'failed'")
            )
            metrics["wf_failed"] = result.scalar() or 0
    except Exception:
        metrics.update(wf_workflows=0, wf_executions=0, wf_failed=0)

    return metrics
