"""Shared session auth + RBAC primitives for service apps."""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import time
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware


ROLE_ORDER = ["viewer", "agent", "manager", "admin", "owner"]
PERMISSION_MIN_ROLE = {
    "dashboard.read": "viewer",
    "dashboard.write": "manager",
    "crm.read": "viewer",
    "crm.write": "manager",
    "workflows.read": "viewer",
    "workflows.write": "manager",
}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@dataclass(frozen=True)
class AuthUser:
    email: str
    role: str


def _normalize_role(role: str) -> str:
    role_norm = (role or "").strip().lower()
    return role_norm if role_norm in ROLE_ORDER else "viewer"


def has_permission(role: str, permission: str) -> bool:
    required = _normalize_role(PERMISSION_MIN_ROLE.get(permission, "owner"))
    actual = _normalize_role(role)
    return ROLE_ORDER.index(actual) >= ROLE_ORDER.index(required)


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * ((4 - (len(data) % 4)) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("utf-8"))


def _get_setting(settings_obj, name: str, default):
    value = getattr(settings_obj, name, default)
    return default if value is None else value


def _cookie_name(settings_obj) -> str:
    return str(_get_setting(settings_obj, "auth_cookie_name", "ml_session"))


def _secret(settings_obj) -> str:
    return str(_get_setting(settings_obj, "auth_secret", "")).strip()


def _auth_enabled(settings_obj) -> bool:
    return bool(_get_setting(settings_obj, "auth_enabled", False))


def _bootstrap_credentials(settings_obj) -> tuple[str, str, str]:
    email = str(_get_setting(settings_obj, "auth_bootstrap_email", "")).strip().lower()
    password = str(_get_setting(settings_obj, "auth_bootstrap_password", ""))
    role = _normalize_role(str(_get_setting(settings_obj, "auth_bootstrap_role", "owner")))
    return email, password, role


def _ttl_seconds(settings_obj) -> int:
    ttl = int(_get_setting(settings_obj, "auth_session_ttl_seconds", 86400))
    return max(60, ttl)


def _cookie_secure(settings_obj) -> bool:
    return bool(_get_setting(settings_obj, "auth_cookie_secure", False))


def issue_session_token(settings_obj, user: AuthUser) -> str:
    secret = _secret(settings_obj)
    if not secret:
        raise RuntimeError("auth_secret is required when auth is enabled")

    now = int(time.time())
    payload = {
        "sub": user.email,
        "role": _normalize_role(user.role),
        "iat": now,
        "exp": now + _ttl_seconds(settings_obj),
    }
    body = _b64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    sig = hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def decode_session_token(settings_obj, token: str) -> AuthUser | None:
    secret = _secret(settings_obj)
    if not secret or not token:
        return None

    try:
        body, provided_sig = token.split(".", 1)
    except ValueError:
        return None

    expected_sig = hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(provided_sig, expected_sig):
        return None

    try:
        payload = json.loads(_b64url_decode(body))
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None

    exp = payload.get("exp")
    sub = payload.get("sub")
    role = payload.get("role")
    if not isinstance(exp, int) or exp <= int(time.time()):
        return None
    if not isinstance(sub, str) or not sub.strip():
        return None
    return AuthUser(email=sub.strip().lower(), role=_normalize_role(str(role)))


def authenticate_bootstrap_user(settings_obj, email: str, password: str) -> AuthUser | None:
    configured_email, configured_password, configured_role = _bootstrap_credentials(settings_obj)
    if not configured_email or not configured_password:
        return None

    email_norm = (email or "").strip().lower()
    password_raw = password or ""
    if hmac.compare_digest(email_norm, configured_email) and hmac.compare_digest(
        password_raw,
        configured_password,
    ):
        return AuthUser(email=configured_email, role=configured_role)
    return None


def _extract_token_from_request(request: Request, settings_obj) -> str:
    cookie_token = request.cookies.get(_cookie_name(settings_obj), "")
    if cookie_token:
        return cookie_token

    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def current_user_from_request(request: Request, settings_obj) -> AuthUser | None:
    return decode_session_token(settings_obj, _extract_token_from_request(request, settings_obj))


def _permission_for(service_name: str, method: str) -> str:
    mode = "read" if method.upper() in SAFE_METHODS else "write"
    return f"{service_name}.{mode}"


def _is_exempt_path(path: str, exempt_prefixes: Iterable[str]) -> bool:
    for raw_prefix in exempt_prefixes:
        prefix = (raw_prefix or "").strip()
        if not prefix:
            continue
        if prefix.endswith("/"):
            if path.startswith(prefix):
                return True
        elif path == prefix or path.startswith(prefix + "/"):
            return True
    return False


def _should_redirect_to_login(request: Request) -> bool:
    if request.url.path.startswith("/api/"):
        return False

    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        return False

    accept = request.headers.get("accept", "").lower()
    if "text/html" in accept or "application/xhtml+xml" in accept:
        return True

    # Browsers often send */* for form submits and HTMX calls.
    return accept in {"", "*/*"}


class RBACMiddleware(BaseHTTPMiddleware):
    """Session auth + coarse role-based authorization middleware."""

    def __init__(
        self,
        app,
        *,
        settings_obj,
        service_name: str,
        exempt_prefixes: Iterable[str] = (),
    ):
        super().__init__(app)
        self._settings_obj = settings_obj
        self._service_name = service_name
        self._exempt_prefixes = tuple(exempt_prefixes)

    async def dispatch(self, request: Request, call_next):
        if not _auth_enabled(self._settings_obj):
            return await call_next(request)

        if _is_exempt_path(request.url.path, self._exempt_prefixes):
            return await call_next(request)

        if not _secret(self._settings_obj):
            return JSONResponse({"detail": "Authentication is misconfigured"}, status_code=503)

        user = current_user_from_request(request, self._settings_obj)
        if not user:
            if _should_redirect_to_login(request):
                path_with_query = request.url.path
                if request.url.query:
                    path_with_query = f"{path_with_query}?{request.url.query}"
                target = quote(path_with_query, safe="/:?=&")
                return RedirectResponse(f"/auth/login?next={target}", status_code=303)
            return JSONResponse({"detail": "Authentication required"}, status_code=401)

        permission = _permission_for(self._service_name, request.method)
        if not has_permission(user.role, permission):
            return JSONResponse({"detail": "Forbidden"}, status_code=403)

        request.state.auth_user = user
        return await call_next(request)


def require_permission(settings_obj, permission: str):
    """FastAPI dependency helper for explicit permission checks."""

    async def _dep(request: Request) -> AuthUser | None:
        if not _auth_enabled(settings_obj):
            return None

        user = current_user_from_request(request, settings_obj)
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")
        if not has_permission(user.role, permission):
            raise HTTPException(status_code=403, detail="Forbidden")
        return user

    return _dep


def build_auth_router(settings_obj, home_path: str = "/") -> APIRouter:
    """Construct login/logout routes for a service app."""
    router = APIRouter(tags=["auth"])

    def _render_login(next_path: str, error: str | None = None) -> HTMLResponse:
        error_html = ""
        if error:
            error_html = f"<p style='color:#b91c1c;margin-bottom:1rem;'>{html.escape(error)}</p>"
        page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sign In</title>
  <style>
    body {{ font-family: system-ui, sans-serif; background:#0b1020; color:#e5e7eb; margin:0; }}
    .wrap {{ min-height:100vh; display:flex; align-items:center; justify-content:center; padding:1rem; }}
    .card {{ width:100%; max-width:420px; background:#111827; border:1px solid #1f2937; border-radius:12px; padding:1.25rem; }}
    .title {{ margin:0 0 .25rem 0; font-size:1.2rem; }}
    .sub {{ margin:0 0 1rem 0; color:#9ca3af; font-size:.9rem; }}
    label {{ display:block; margin:.75rem 0 .25rem 0; font-size:.9rem; }}
    input {{ width:100%; padding:.6rem .7rem; border-radius:8px; border:1px solid #374151; background:#0f172a; color:#f3f4f6; }}
    button {{ margin-top:1rem; width:100%; padding:.65rem .8rem; border:0; border-radius:8px; background:#2563eb; color:#fff; font-weight:600; cursor:pointer; }}
  </style>
</head>
<body>
  <div class="wrap">
    <form method="post" class="card">
      <h1 class="title">Sign In</h1>
      <p class="sub">MaxLevel service access</p>
      {error_html}
      <input type="hidden" name="next" value="{html.escape(next_path)}">
      <label for="email">Email</label>
      <input id="email" name="email" type="email" required autocomplete="username">
      <label for="password">Password</label>
      <input id="password" name="password" type="password" required autocomplete="current-password">
      <button type="submit">Sign in</button>
    </form>
  </div>
</body>
</html>"""
        return HTMLResponse(page)

    @router.get("/auth/login")
    async def login_page(request: Request, next: str = home_path):  # noqa: A002
        if not _auth_enabled(settings_obj):
            return RedirectResponse(home_path, status_code=303)
        if current_user_from_request(request, settings_obj):
            return RedirectResponse(next or home_path, status_code=303)
        if not _secret(settings_obj):
            return HTMLResponse("Authentication is misconfigured", status_code=503)
        return _render_login(next)

    @router.post("/auth/login")
    async def login_submit(request: Request):
        if not _auth_enabled(settings_obj):
            return RedirectResponse(home_path, status_code=303)
        if not _secret(settings_obj):
            return HTMLResponse("Authentication is misconfigured", status_code=503)

        form = await request.form()
        email = str(form.get("email", "")).strip()
        password = str(form.get("password", ""))
        next_path = str(form.get("next", home_path)).strip() or home_path
        if not next_path.startswith("/"):
            next_path = home_path

        user = authenticate_bootstrap_user(settings_obj, email=email, password=password)
        if not user:
            return _render_login(next_path, error="Invalid credentials")

        token = issue_session_token(settings_obj, user)
        response = RedirectResponse(next_path, status_code=303)
        response.set_cookie(
            key=_cookie_name(settings_obj),
            value=token,
            max_age=_ttl_seconds(settings_obj),
            httponly=True,
            secure=_cookie_secure(settings_obj),
            samesite="lax",
            path="/",
        )
        return response

    @router.post("/auth/logout")
    async def logout_post():
        response = RedirectResponse("/auth/login", status_code=303)
        response.delete_cookie(_cookie_name(settings_obj), path="/")
        return response

    @router.get("/auth/logout")
    async def logout_get():
        response = RedirectResponse("/auth/login", status_code=303)
        response.delete_cookie(_cookie_name(settings_obj), path="/")
        return response

    return router

