"""FastAPI application factory for the Unified Dashboard."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from maxlevel.platform_auth import RBACMiddleware, build_auth_router

from .config import settings
from .database import multi_db
from .services import auth_svc


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await multi_db.dispose()


app = FastAPI(title=settings.app_title, lifespan=lifespan)

app.add_middleware(
    RBACMiddleware,
    settings_obj=settings,
    service_name="dashboard",
    resolve_user_fn=auth_svc.resolve_user,
    exempt_prefixes=(
        "/health",
        "/ready",
        "/static/",
        "/auth/login",
        "/auth/logout",
        "/auth/invites",
        "/auth/users",
        "/auth/password",
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
        allow_bootstrap_fallback=False,
        resolve_user_fn=auth_svc.resolve_user,
        authenticate_fn=auth_svc.authenticate_user,
        audit_log_fn=auth_svc.record_auth_event,
    )
)
