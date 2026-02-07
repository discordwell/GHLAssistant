"""Dashboard router — workflow list page."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..app import templates
from ..database import get_db
from ..services import workflow_svc

router = APIRouter()


@router.get("/")
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    workflows = await workflow_svc.list_workflows(db)
    return templates.TemplateResponse(
        "dashboard/index.html",
        {"request": request, "workflows": workflows},
    )
