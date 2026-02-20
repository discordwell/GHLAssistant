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
    if settings.auth_enabled and (settings.is_production or settings.security_fail_closed):
        if not await auth_svc.has_active_owner():
            raise RuntimeError(
                "Dashboard auth enabled in production/fail-closed mode but no active owner exists. "
                "Run `maxlevel auth bootstrap-owner --service crm` before starting."
            )
    yield
    await multi_db.dispose()


app = FastAPI(title=settings.app_title, lifespan=lifespan)

app.add_middleware(
    RBACMiddleware,
    settings_obj=settings,
    service_name="dashboard",
    resolve_user_fn=auth_svc.resolve_user,
    validate_session_fn=auth_svc.validate_session,
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
        "/auth/forgot",
        "/auth/reset",
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
        create_session_fn=auth_svc.create_session,
        validate_session_fn=auth_svc.validate_session,
        list_sessions_fn=auth_svc.list_sessions,
        revoke_session_fn=auth_svc.revoke_session,
        revoke_all_sessions_fn=auth_svc.revoke_all_sessions,
        request_password_reset_fn=auth_svc.request_password_reset,
        reset_password_fn=auth_svc.reset_password,
        list_audit_events_fn=auth_svc.list_auth_events,
        audit_log_fn=auth_svc.record_auth_event,
    )
)
