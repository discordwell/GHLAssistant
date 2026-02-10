"""Import tasks from GHL."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.contact import Contact
from ..models.location import Location
from ..models.task import Task
from ..schemas.sync import SyncResult
from .raw_store import upsert_raw_entity


def _extract_ghl_id(payload: dict) -> str:
    for key in ("id", "_id"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _parse_due_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        ts = float(value)
        # Heuristic: milliseconds vs seconds
        if ts > 1_000_000_000_000:
            ts = ts / 1000.0
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc).date()
        except Exception:
            return None
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            # ISO datetime
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
        except ValueError:
            pass
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            return None
    return None


def _extract_assigned_to(payload: dict) -> str | None:
    def _scan(d: dict) -> str | None:
        for key in ("assignedTo", "assignedToName", "assignedUser", "assignedUserId"):
            value = d.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    hit = _scan(payload)
    if hit:
        return hit
    props = payload.get("properties")
    if isinstance(props, dict):
        return _scan(props)
    return None


async def _resolve_contact_id(
    db: AsyncSession,
    *,
    location: Location,
    ghl_contact_id: str,
    contact_map: dict[str, uuid.UUID] | None,
) -> uuid.UUID | None:
    if contact_map and ghl_contact_id in contact_map:
        return contact_map[ghl_contact_id]
    stmt = select(Contact).where(
        Contact.location_id == location.id,
        Contact.ghl_id == ghl_contact_id,
    )
    contact = (await db.execute(stmt)).scalar_one_or_none()
    return contact.id if contact else None


async def import_tasks(
    db: AsyncSession,
    location: Location,
    tasks_by_contact: dict[str, list[dict]],
    contact_map: dict[str, uuid.UUID] | None = None,
) -> SyncResult:
    """Import tasks grouped by GHL contact id."""
    result = SyncResult()
    now = datetime.now(timezone.utc)

    for ghl_contact_id, tasks in (tasks_by_contact or {}).items():
        if not isinstance(ghl_contact_id, str) or not ghl_contact_id:
            continue
        if not isinstance(tasks, list) or not tasks:
            continue

        local_contact_id = await _resolve_contact_id(
            db,
            location=location,
            ghl_contact_id=ghl_contact_id,
            contact_map=contact_map,
        )

        for task_payload in tasks:
            if not isinstance(task_payload, dict):
                continue
            ghl_id = _extract_ghl_id(task_payload)
            if not ghl_id:
                continue

            await upsert_raw_entity(
                db,
                location=location,
                entity_type="task",
                ghl_id=ghl_id,
                payload=task_payload,
            )

            props = task_payload.get("properties")
            if not isinstance(props, dict):
                props = {}

            # services.leadconnectorhq.com task records nest fields under `properties`.
            title = props.get("title") or task_payload.get("title") or task_payload.get("name") or ""
            if not isinstance(title, str):
                title = str(title)

            description = props.get("description")
            if description is None:
                description = task_payload.get("description")
            if description is None:
                description = props.get("body")
            if description is None:
                description = task_payload.get("body")
            if description is not None and not isinstance(description, str):
                description = str(description)

            status = task_payload.get("status")
            if status is None:
                status = props.get("status")

            completed_val = task_payload.get("completed")
            if not isinstance(completed_val, bool):
                completed_val = props.get("completed")
            if isinstance(completed_val, bool):
                status = "done" if completed_val else (status or "pending")
            if not isinstance(status, str) or not status.strip():
                status = "pending"

            priority = task_payload.get("priority")
            if priority is None:
                priority = props.get("priority")
            if isinstance(priority, bool):
                priority = int(priority)
            if not isinstance(priority, int):
                priority = 0

            due_date = _parse_due_date(
                task_payload.get("dueDate")
                or task_payload.get("due_date")
                or props.get("dueDate")
                or props.get("due_date")
            )

            stmt = select(Task).where(
                Task.location_id == location.id,
                Task.ghl_id == ghl_id,
            )
            task = (await db.execute(stmt)).scalar_one_or_none()

            if task:
                task.title = title
                task.description = description
                task.status = status
                task.priority = priority
                task.due_date = due_date
                task.assigned_to = _extract_assigned_to(task_payload)
                if local_contact_id is not None:
                    task.contact_id = local_contact_id
                task.last_synced_at = now
                result.updated += 1
            else:
                task = Task(
                    location_id=location.id,
                    title=title,
                    description=description,
                    contact_id=local_contact_id,
                    due_date=due_date,
                    status=status,
                    priority=priority,
                    assigned_to=_extract_assigned_to(task_payload),
                    ghl_id=ghl_id,
                    ghl_location_id=location.ghl_location_id,
                    last_synced_at=now,
                )
                db.add(task)
                result.created += 1

    await db.commit()
    return result
