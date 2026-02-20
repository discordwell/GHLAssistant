"""FastAPI application factory for Workflow Builder."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from maxlevel.platform_auth import RBACMiddleware, build_auth_router

from .config import settings
from .worker import dispatch_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-create tables for SQLite (local dev)
    if "sqlite" in settings.database_url:
        from .database import engine
        from .models import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    dispatch_worker.start()
    yield
    await dispatch_worker.stop()


app = FastAPI(title=settings.app_title, lifespan=lifespan)

app.add_middleware(
    RBACMiddleware,
    settings_obj=settings,
    service_name="workflows",
    exempt_prefixes=(
        "/health",
        "/ready",
        "/static/",
        "/auth/login",
        "/auth/logout",
        "/webhooks/",
    ),
)
app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="wf_static")

templates = Jinja2Templates(directory=str(settings.templates_dir))
templates.env.globals["app_urls"] = settings.app_urls

# Import and register routers
from .routers import (  # noqa: E402
    api,
    chat,
    dashboard,
    editor,
    executions,
    health,
    webhooks,
    workflows,
)

app.include_router(dashboard.router)
app.include_router(workflows.router)
app.include_router(editor.router)
app.include_router(executions.router)
app.include_router(api.router)
app.include_router(chat.router)
app.include_router(webhooks.router)
app.include_router(health.router)
app.include_router(build_auth_router(settings, home_path="/"))
