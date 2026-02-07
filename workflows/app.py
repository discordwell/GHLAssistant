"""FastAPI application factory for Workflow Builder."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-create tables for SQLite (local dev)
    if "sqlite" in settings.database_url:
        from .database import engine
        from .models import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title=settings.app_title, lifespan=lifespan)

app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="wf_static")

templates = Jinja2Templates(directory=str(settings.templates_dir))

# Import and register routers
from .routers import dashboard, workflows, editor, executions, api, chat, webhooks  # noqa: E402

app.include_router(dashboard.router)
app.include_router(workflows.router)
app.include_router(editor.router)
app.include_router(executions.router)
app.include_router(api.router)
app.include_router(chat.router)
app.include_router(webhooks.router)
