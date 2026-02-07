"""FastAPI application factory for CRM Platform."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import settings
from .tenant.middleware import TenantMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tables managed by Alembic migrations — nothing to do on startup
    yield


app = FastAPI(title=settings.app_title, lifespan=lifespan)

app.add_middleware(TenantMiddleware)
app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")

templates = Jinja2Templates(directory=str(settings.templates_dir))

# Import and register routers
from .routers import locations, dashboard, contacts, pipelines, tags, custom_fields, tasks, sync  # noqa: E402

app.include_router(locations.router)
app.include_router(dashboard.router)
app.include_router(contacts.router)
app.include_router(pipelines.router)
app.include_router(tags.router)
app.include_router(custom_fields.router)
app.include_router(tasks.router)
app.include_router(sync.router)
