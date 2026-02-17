"""Health check router — JSON status for all app databases."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from sqlalchemy import text

from .. import database as _db_module

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check():
    db = _db_module.multi_db
    status = {"dashboard": "ok"}

    # CRM
    try:
        async with db.crm_session() as session:
            await session.execute(text("SELECT 1"))
        status["crm"] = "ok"
    except Exception:
        logger.warning("CRM health check failed", exc_info=True)
        status["crm"] = "error"

    # Workflows
    try:
        async with db.wf_session() as session:
            await session.execute(text("SELECT 1"))
        status["workflows"] = "ok"
    except Exception:
        logger.warning("Workflows health check failed", exc_info=True)
        status["workflows"] = "error"

    # Hiring
    try:
        with db.hiring_connection() as conn:
            conn.execute(text("SELECT 1"))
        status["hiring"] = "ok"
    except Exception:
        logger.warning("Hiring health check failed", exc_info=True)
        status["hiring"] = "error"

    overall = all(v == "ok" for v in status.values())
    return {"status": "healthy" if overall else "degraded", "services": status}


@router.get("/ready")
async def readiness_check():
    result = await health_check()
    if result["status"] == "healthy":
        return {"status": "ready", "services": result["services"]}
    return {"status": "not_ready", "services": result["services"]}
