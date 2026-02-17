"""Task management routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..models.location import Location
from ..services import task_svc, activity_svc
from ..tenant.deps import get_current_location

router = APIRouter(tags=["tasks"])
templates = Jinja2Templates(directory=str(settings.templates_dir))
templates.env.globals["app_urls"] = settings.app_urls

def _safe_next_url(value: object) -> str | None:
    """Allow only local relative redirect targets to avoid open redirects."""
    if not isinstance(value, str):
        return None
    v = value.strip()
    if not v or not v.startswith("/"):
        return None
    if v.startswith("//") or "://" in v:
        return None
    return v


@router.get("/loc/{slug}/tasks/")
async def task_list(
    request: Request,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
    status: str | None = None,
):
    tasks = await task_svc.list_tasks(db, location.id, status=status)
    locations = list((await db.execute(select(Location).order_by(Location.name))).scalars().all())
    return templates.TemplateResponse("tasks/list.html", {
        "request": request,
        "location": location,
        "locations": locations,
        "tasks": tasks,
        "current_status": status or "",
    })


@router.post("/loc/{slug}/tasks/")
async def task_create(
    request: Request,
    slug: str,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    title = form.get("title", "").strip()
    description = form.get("description", "").strip() or None
    due_date = form.get("due_date", "").strip() or None
    try:
        priority = int(form.get("priority", "0"))
    except (TypeError, ValueError):
        priority = 0
    assigned_to = form.get("assigned_to", "").strip() or None
    contact_id_str = form.get("contact_id", "")
    try:
        contact_id = uuid.UUID(contact_id_str) if contact_id_str else None
    except (TypeError, ValueError):
        contact_id = None

    # Defensive: ensure contact belongs to this location before linking.
    if contact_id is not None:
        from ..models.contact import Contact

        stmt = select(Contact).where(Contact.id == contact_id, Contact.location_id == location.id)
        contact = (await db.execute(stmt)).scalar_one_or_none()
        if contact is None:
            contact_id = None

    if title:
        task = await task_svc.create_task(
            db, location.id,
            title=title, description=description, due_date=due_date,
            priority=priority, assigned_to=assigned_to, contact_id=contact_id,
        )
        await activity_svc.log_activity(
            db, location.id, "task", task.id, "created",
            description=f"Task '{title}' created"
        )
    next_url = _safe_next_url(form.get("next"))
    if next_url:
        return RedirectResponse(next_url, status_code=303)
    return RedirectResponse(f"/loc/{slug}/tasks/", status_code=303)


@router.post("/loc/{slug}/tasks/{task_id}/status")
async def task_update_status(
    request: Request,
    slug: str,
    task_id: uuid.UUID,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    new_status = form.get("status", "pending")
    # Verify task belongs to this location.
    from ..models.task import Task

    stmt = select(Task).where(Task.id == task_id, Task.location_id == location.id)
    task = (await db.execute(stmt)).scalar_one_or_none()
    if task:
        await task_svc.update_task(db, task_id, status=new_status)
    next_url = _safe_next_url(form.get("next"))
    if next_url:
        return RedirectResponse(next_url, status_code=303)
    return RedirectResponse(f"/loc/{slug}/tasks/", status_code=303)


@router.post("/loc/{slug}/tasks/{task_id}/delete")
async def task_delete(
    slug: str,
    task_id: uuid.UUID,
    location: Location = Depends(get_current_location),
    db: AsyncSession = Depends(get_db),
):
    # Verify task belongs to this location
    from ..models.task import Task
    stmt = select(Task).where(Task.id == task_id, Task.location_id == location.id)
    task = (await db.execute(stmt)).scalar_one_or_none()
    if task:
        await task_svc.delete_task(db, task_id)
    return RedirectResponse(f"/loc/{slug}/tasks/", status_code=303)
