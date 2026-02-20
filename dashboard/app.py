"""FastAPI application factory for the Unified Dashboard."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from maxlevel.platform_auth import RBACMiddleware, build_auth_router

from .config import settings
from .database import multi_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await multi_db.dispose()


app = FastAPI(title=settings.app_title, lifespan=lifespan)

app.add_middleware(
    RBACMiddleware,
    settings_obj=settings,
    service_name="dashboard",
    exempt_prefixes=(
        "/health",
        "/ready",
        "/static/",
        "/auth/login",
        "/auth/logout",
        "/auth/invites",
        "/auth/accept",
    ),
)
app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="dash_static")

templates = Jinja2Templates(directory=str(settings.templates_dir))
templates.env.globals["app_urls"] = settings.app_urls

# Import and register routers
from .routers import home, health  # noqa: E402

app.include_router(home.router)
app.include_router(health.router)
app.include_router(
    build_auth_router(
        settings,
        service_name="dashboard",
        home_path="/",
    )
)
