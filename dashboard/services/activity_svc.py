"""Merge activity feeds from all 3 app databases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text

from ..database import MultiDB
from .. import database as _db_module


@dataclass
class ActivityItem:
    source: str  # "crm", "hiring", "workflows"
    action: str
    description: str
    timestamp: datetime


async def get_recent_activity(
    db: MultiDB | None = None, limit: int = 50
) -> list[ActivityItem]:
    """Merge recent activity entries from all 3 databases, sorted by timestamp desc."""
    db = db or _db_module.multi_db
    items: list[ActivityItem] = []

    # CRM activities
    try:
        async with db.crm_session() as session:
            result = await session.execute(
                text(
                    "SELECT action, description, created_at "
                    "FROM activity ORDER BY created_at DESC LIMIT :limit"
                ),
                {"limit": limit},
            )
            for row in result:
                items.append(
                    ActivityItem(
                        source="crm",
                        action=row[0] or "",
                        description=row[1] or "",
                        timestamp=_parse_ts(row[2]),
                    )
                )
    except Exception:
        pass

    # Hiring activities
    try:
        with db.hiring_connection() as conn:
            result = conn.execute(
                text(
                    "SELECT activity_type, description, created_at "
                    "FROM candidateactivity ORDER BY created_at DESC LIMIT :limit"
                ),
                {"limit": limit},
            )
            for row in result:
                items.append(
                    ActivityItem(
                        source="hiring",
                        action=row[0] or "",
                        description=row[1] or "",
                        timestamp=_parse_ts(row[2]),
                    )
                )
    except Exception:
        pass

    # Workflow logs
    try:
        async with db.wf_session() as session:
            result = await session.execute(
                text(
                    "SELECT event, message, created_at "
                    "FROM workflow_log ORDER BY created_at DESC LIMIT :limit"
                ),
                {"limit": limit},
            )
            for row in result:
                items.append(
                    ActivityItem(
                        source="workflows",
                        action=row[0] or "",
                        description=row[1] or "",
                        timestamp=_parse_ts(row[2]),
                    )
                )
    except Exception:
        pass

    # Sort all items by timestamp descending and trim to limit
    items.sort(key=lambda x: x.timestamp, reverse=True)
    return items[:limit]


def _parse_ts(value) -> datetime:
    """Parse a timestamp from DB — handles both datetime objects and ISO strings."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        # Handle ISO format with or without timezone
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return datetime.min
    return datetime.min
