"""FastAPI application factory for Workflow Builder."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from maxlevel.platform_auth import RBACMiddleware, build_auth_router

from .config import settings
from .services import auth_svc
from .worker import dispatch_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-create tables for SQLite (local dev)
    if "sqlite" in settings.database_url:
        from .database import engine
        from .models import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    if settings.auth_enabled and (settings.is_production or settings.security_fail_closed):
        if not await auth_svc.has_active_owner():
            raise RuntimeError(
                "Auth enabled in production/fail-closed mode but no active owner exists. "
                "Run `maxlevel auth bootstrap-owner --service workflows` before starting."
            )
    dispatch_worker.start()
    yield
    await dispatch_worker.stop()


app = FastAPI(title=settings.app_title, lifespan=lifespan)

app.add_middleware(
    RBACMiddleware,
    settings_obj=settings,
    service_name="workflows",
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
app.include_router(
    build_auth_router(
        settings,
        service_name="workflows",
        home_path="/",
        allow_bootstrap_fallback=False,
        resolve_user_fn=auth_svc.resolve_user,
        authenticate_fn=auth_svc.authenticate_user,
        list_invites_fn=auth_svc.list_invites,
        create_invite_fn=auth_svc.create_invite,
        accept_invite_fn=auth_svc.accept_invite,
        list_accounts_fn=auth_svc.list_accounts,
        update_account_fn=auth_svc.update_account,
        change_password_fn=auth_svc.change_password,
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
