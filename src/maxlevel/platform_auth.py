"""Shared session auth + RBAC primitives for service apps."""

from __future__ import annotations

import base64
import binascii
import datetime as dt
import hashlib
import hmac
import html
import inspect
import json
import secrets
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


def hash_password(password: str, iterations: int = 200_000) -> str:
    """Hash a password using PBKDF2-SHA256."""
    if not password:
        raise ValueError("Password is required")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return (
        f"pbkdf2_sha256${iterations}$"
        f"{binascii.hexlify(salt).decode('ascii')}$"
        f"{binascii.hexlify(digest).decode('ascii')}"
    )


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a PBKDF2-SHA256 password hash."""
    if not password or not stored_hash:
        return False
    try:
        scheme, iterations_raw, salt_hex, digest_hex = stored_hash.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        iterations = int(iterations_raw)
        salt = binascii.unhexlify(salt_hex.encode("ascii"))
        expected = binascii.unhexlify(digest_hex.encode("ascii"))
    except Exception:
        return False

    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def issue_invite_token() -> str:
    return secrets.token_urlsafe(32)


def hash_invite_token(token: str) -> str:
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


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


def build_auth_router(
    settings_obj,
    *,
    service_name: str,
    home_path: str = "/",
    authenticate_fn=None,
    list_invites_fn=None,
    create_invite_fn=None,
    accept_invite_fn=None,
) -> APIRouter:
    """Construct login/logout routes for a service app."""
    router = APIRouter(tags=["auth"])

    async def _maybe_await(value):
        return await value if inspect.isawaitable(value) else value

    def _supports_request_arg(callback) -> bool:
        if not callback:
            return False
        try:
            sig = inspect.signature(callback)
        except (TypeError, ValueError):
            return False
        if "request" in sig.parameters:
            return True
        return any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        )

    async def _invoke_callback(callback, *args, request: Request | None = None):
        if not callback:
            return None
        kwargs = {"request": request} if request and _supports_request_arg(callback) else {}
        return await _maybe_await(callback(*args, **kwargs))

    async def _authenticate(request: Request, email: str, password: str) -> AuthUser | None:
        if authenticate_fn:
            user = await _invoke_callback(authenticate_fn, email, password, request=request)
            if user:
                return user
        return authenticate_bootstrap_user(settings_obj, email=email, password=password)

    def _can_manage_users(user: AuthUser | None) -> bool:
        if not user:
            return False
        return has_permission(user.role, f"{service_name}.write")

    def _fmt_dt(value) -> str:
        if isinstance(value, dt.datetime):
            return value.strftime("%Y-%m-%d %H:%M UTC")
        if isinstance(value, str):
            return value
        return "-"

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

        user = await _authenticate(request=request, email=email, password=password)
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

    @router.get("/auth/invites")
    async def invites_page(request: Request, token: str = "", msg: str = ""):
        if not _auth_enabled(settings_obj):
            return RedirectResponse(home_path, status_code=303)
        if not create_invite_fn or not list_invites_fn:
            return HTMLResponse("Invite flow is not configured", status_code=404)

        user = current_user_from_request(request, settings_obj)
        if not _can_manage_users(user):
            return RedirectResponse("/auth/login", status_code=303)

        invites = await _invoke_callback(list_invites_fn, request=request)
        invite_rows = []
        for invite in invites or []:
            invite_rows.append(
                "<tr>"
                f"<td style='padding:.4rem;border-top:1px solid #1f2937;'>{html.escape(str(invite.get('email', '')))}</td>"
                f"<td style='padding:.4rem;border-top:1px solid #1f2937;'>{html.escape(str(invite.get('role', '')))}</td>"
                f"<td style='padding:.4rem;border-top:1px solid #1f2937;'>{html.escape(str(invite.get('status', '')))}</td>"
                f"<td style='padding:.4rem;border-top:1px solid #1f2937;'>{html.escape(_fmt_dt(invite.get('expires_at')))}</td>"
                "</tr>"
            )
        invite_table = "".join(invite_rows) or (
            "<tr><td colspan='4' style='padding:.6rem;color:#9ca3af;'>No invites yet</td></tr>"
        )

        token_block = ""
        if token:
            base = str(request.base_url).rstrip("/")
            link = f"{base}/auth/accept?token={quote(token, safe='')}"
            token_block = (
                "<div style='background:#0f172a;border:1px solid #1f2937;border-radius:8px;padding:.75rem;margin:1rem 0;'>"
                "<div style='font-weight:600;margin-bottom:.35rem;'>Invite Link</div>"
                f"<code style='word-break:break-all;'>{html.escape(link)}</code>"
                "</div>"
            )

        message_block = ""
        if msg:
            message_block = f"<p style='color:#22c55e;margin:.5rem 0 0 0;'>{html.escape(msg)}</p>"

        page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>User Invites</title>
<style>
body {{ font-family: system-ui, sans-serif; background:#0b1020; color:#e5e7eb; margin:0; }}
.wrap {{ max-width:860px; margin:1.5rem auto; padding:0 1rem; }}
.card {{ background:#111827; border:1px solid #1f2937; border-radius:12px; padding:1rem; margin-bottom:1rem; }}
input, select {{ width:100%; padding:.6rem .7rem; border-radius:8px; border:1px solid #374151; background:#0f172a; color:#f3f4f6; }}
button {{ padding:.6rem .9rem; border:0; border-radius:8px; background:#2563eb; color:white; font-weight:600; cursor:pointer; }}
table {{ width:100%; border-collapse:collapse; font-size:.92rem; }}
a {{ color:#60a5fa; }}
</style></head><body>
<div class="wrap">
  <div class="card">
    <h1 style="margin:0 0 .25rem 0;">User Invites</h1>
    <p style="margin:0;color:#9ca3af;">Create invite links for new users.</p>
    {message_block}
    {token_block}
    <form method="post" action="/auth/invites" style="margin-top:.8rem;display:grid;grid-template-columns:2fr 1fr auto;gap:.6rem;align-items:end;">
      <div><label>Email</label><input type="email" name="email" required></div>
      <div><label>Role</label>
        <select name="role">
          <option value="viewer">viewer</option>
          <option value="agent">agent</option>
          <option value="manager">manager</option>
          <option value="admin">admin</option>
          <option value="owner">owner</option>
        </select>
      </div>
      <div><button type="submit">Create Invite</button></div>
    </form>
  </div>
  <div class="card">
    <h2 style="margin:0 0 .75rem 0;font-size:1.05rem;">Recent Invites</h2>
    <table>
      <thead><tr><th align="left">Email</th><th align="left">Role</th><th align="left">Status</th><th align="left">Expires</th></tr></thead>
      <tbody>{invite_table}</tbody>
    </table>
  </div>
  <p><a href="{html.escape(home_path)}">Back to app</a></p>
</div></body></html>"""
        return HTMLResponse(page)

    @router.post("/auth/invites")
    async def create_invite(request: Request):
        if not _auth_enabled(settings_obj):
            return RedirectResponse(home_path, status_code=303)
        if not create_invite_fn:
            return HTMLResponse("Invite flow is not configured", status_code=404)

        user = current_user_from_request(request, settings_obj)
        if not _can_manage_users(user):
            return RedirectResponse("/auth/login", status_code=303)

        form = await request.form()
        email = str(form.get("email", "")).strip().lower()
        role = _normalize_role(str(form.get("role", "viewer")))
        if not email:
            return RedirectResponse("/auth/invites?msg=Email+required", status_code=303)

        token = await _invoke_callback(
            create_invite_fn,
            email,
            role,
            user.email,
            request=request,
        )
        return RedirectResponse(
            f"/auth/invites?msg=Invite+created&token={quote(token or '', safe='')}",
            status_code=303,
        )

    @router.get("/auth/accept")
    async def accept_page(token: str = ""):
        if not _auth_enabled(settings_obj):
            return RedirectResponse(home_path, status_code=303)
        if not accept_invite_fn:
            return HTMLResponse("Invite acceptance is not configured", status_code=404)

        token_safe = html.escape(token)
        page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Accept Invite</title>
<style>
body {{ font-family: system-ui, sans-serif; background:#0b1020; color:#e5e7eb; margin:0; }}
.wrap {{ min-height:100vh; display:flex; align-items:center; justify-content:center; padding:1rem; }}
.card {{ width:100%; max-width:420px; background:#111827; border:1px solid #1f2937; border-radius:12px; padding:1.25rem; }}
input {{ width:100%; padding:.6rem .7rem; border-radius:8px; border:1px solid #374151; background:#0f172a; color:#f3f4f6; }}
button {{ margin-top:1rem; width:100%; padding:.65rem .8rem; border:0; border-radius:8px; background:#2563eb; color:#fff; font-weight:600; cursor:pointer; }}
</style></head><body><div class="wrap"><form method="post" class="card">
<h1 style="margin:0 0 .35rem 0;">Accept Invite</h1>
<p style="margin:0 0 .9rem 0;color:#9ca3af;">Set a password to activate your account.</p>
<input type="hidden" name="token" value="{token_safe}">
<label for="password">Password</label>
<input id="password" name="password" type="password" required minlength="8" autocomplete="new-password">
<button type="submit">Activate Account</button>
</form></div></body></html>"""
        return HTMLResponse(page)

    @router.post("/auth/accept")
    async def accept_submit(request: Request):
        if not _auth_enabled(settings_obj):
            return RedirectResponse(home_path, status_code=303)
        if not accept_invite_fn:
            return HTMLResponse("Invite acceptance is not configured", status_code=404)

        form = await request.form()
        token = str(form.get("token", "")).strip()
        password = str(form.get("password", ""))
        if not token or len(password) < 8:
            return HTMLResponse("Invalid invite or password too short", status_code=400)

        user = await _invoke_callback(accept_invite_fn, token, password, request=request)
        if not user:
            return HTMLResponse("Invite is invalid, expired, or already used", status_code=400)

        session_token = issue_session_token(settings_obj, user)
        response = RedirectResponse(home_path, status_code=303)
        response.set_cookie(
            key=_cookie_name(settings_obj),
            value=session_token,
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
