"""FastAPI application factory for CRM Platform."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from maxlevel.platform_auth import RBACMiddleware, build_auth_router

from .config import settings
from .tenant.middleware import TenantMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-create tables for SQLite (local dev); PostgreSQL uses Alembic migrations
    if "sqlite" in settings.database_url:
        from .database import engine
        from .models import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title=settings.app_title, lifespan=lifespan)

app.add_middleware(TenantMiddleware)
app.add_middleware(
    RBACMiddleware,
    settings_obj=settings,
    service_name="crm",
    exempt_prefixes=(
        "/health",
        "/ready",
        "/static/",
        "/auth/login",
        "/auth/logout",
        "/auth/invites",
        "/auth/users",
        "/auth/accept",
        "/webhooks/",
        "/f/",
    ),
)
app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")

templates = Jinja2Templates(directory=str(settings.templates_dir))
templates.env.globals["app_urls"] = settings.app_urls

# Import and register routers
from .routers import (  # noqa: E402
    locations, dashboard, contacts, pipelines, tags, custom_fields, tasks, sync,
    conversations, calendars, forms, surveys, campaigns, funnels, health, webhooks,
)
from .services import auth_svc  # noqa: E402

app.include_router(locations.router)
app.include_router(dashboard.router)
app.include_router(contacts.router)
app.include_router(pipelines.router)
app.include_router(tags.router)
app.include_router(custom_fields.router)
app.include_router(tasks.router)
app.include_router(sync.router)
app.include_router(conversations.router)
app.include_router(calendars.router)
app.include_router(forms.router)
app.include_router(surveys.router)
app.include_router(campaigns.router)
app.include_router(funnels.router)
app.include_router(webhooks.router)
app.include_router(health.router)
app.include_router(
    build_auth_router(
        settings,
        service_name="crm",
        home_path="/locations/",
        authenticate_fn=auth_svc.authenticate_user,
        list_invites_fn=auth_svc.list_invites,
        create_invite_fn=auth_svc.create_invite,
        accept_invite_fn=auth_svc.accept_invite,
        list_accounts_fn=auth_svc.list_accounts,
        update_account_fn=auth_svc.update_account,
    )
)
