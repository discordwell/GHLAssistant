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
from collections import deque
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import quote, urlsplit

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


@dataclass
class _AttemptState:
    failures: deque[float]
    blocked_until: float


class _AttemptLimiter:
    def __init__(self):
        self._states: dict[str, _AttemptState] = {}

    def is_blocked(self, key: str, now: float) -> bool:
        state = self._states.get(key)
        if not state:
            return False
        if state.blocked_until > now:
            return True
        if state.blocked_until and state.blocked_until <= now and not state.failures:
            self._states.pop(key, None)
        return False

    def add_failure(
        self,
        *,
        key: str,
        now: float,
        window_seconds: int,
        max_attempts: int,
        block_seconds: int,
    ) -> bool:
        if max_attempts <= 0:
            return False

        state = self._states.get(key)
        if not state:
            state = _AttemptState(failures=deque(), blocked_until=0.0)
            self._states[key] = state

        if state.blocked_until > now:
            return True

        cutoff = now - max(1, window_seconds)
        while state.failures and state.failures[0] < cutoff:
            state.failures.popleft()

        state.failures.append(now)
        if len(state.failures) >= max_attempts:
            state.failures.clear()
            state.blocked_until = now + max(1, block_seconds)
            return True
        return False

    def clear(self, key: str):
        self._states.pop(key, None)


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


def _csrf_cookie_name(settings_obj) -> str:
    return f"{_cookie_name(settings_obj)}_csrf"


def _csrf_token_from_request(request: Request, settings_obj) -> str:
    return (request.cookies.get(_csrf_cookie_name(settings_obj), "") or "").strip()


def _ensure_csrf_token(request: Request, settings_obj) -> str:
    token = _csrf_token_from_request(request, settings_obj)
    return token or secrets.token_urlsafe(32)


def _set_csrf_cookie(response, settings_obj, token: str):
    response.set_cookie(
        key=_csrf_cookie_name(settings_obj),
        value=token,
        max_age=_ttl_seconds(settings_obj),
        httponly=True,
        secure=_cookie_secure(settings_obj),
        samesite="lax",
        path="/",
    )


def _valid_csrf(request: Request, settings_obj, provided_token: str) -> bool:
    cookie_token = _csrf_token_from_request(request, settings_obj)
    provided = (provided_token or "").strip()
    return bool(cookie_token and provided and hmac.compare_digest(cookie_token, provided))


def _sanitize_next_path(raw_next: str, home_path: str) -> str:
    next_path = (raw_next or "").strip()
    if not next_path:
        return home_path
    if "\\" in next_path:
        return home_path
    parsed = urlsplit(next_path)
    if parsed.scheme or parsed.netloc:
        return home_path
    if not next_path.startswith("/") or next_path.startswith("//"):
        return home_path
    return next_path


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
        resolve_user_fn=None,
    ):
        super().__init__(app)
        self._settings_obj = settings_obj
        self._service_name = service_name
        self._exempt_prefixes = tuple(exempt_prefixes)
        self._resolve_user_fn = resolve_user_fn

    async def dispatch(self, request: Request, call_next):
        if not _auth_enabled(self._settings_obj):
            return await call_next(request)

        if _is_exempt_path(request.url.path, self._exempt_prefixes):
            return await call_next(request)

        if not _secret(self._settings_obj):
            return JSONResponse({"detail": "Authentication is misconfigured"}, status_code=503)

        user = current_user_from_request(request, self._settings_obj)
        if user and self._resolve_user_fn:
            resolved = await _invoke_callback(self._resolve_user_fn, user.email, request=request)
            user = resolved if isinstance(resolved, AuthUser) else None
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
    allow_bootstrap_fallback: bool = True,
    resolve_user_fn=None,
    authenticate_fn=None,
    list_invites_fn=None,
    create_invite_fn=None,
    accept_invite_fn=None,
    list_accounts_fn=None,
    update_account_fn=None,
    change_password_fn=None,
    audit_log_fn=None,
) -> APIRouter:
    """Construct login/logout routes for a service app."""
    router = APIRouter(tags=["auth"])
    limiter = _AttemptLimiter()

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

    async def _audit(
        action: str,
        outcome: str,
        *,
        actor_email: str | None = None,
        target_email: str | None = None,
        details=None,
        request: Request | None = None,
    ) -> None:
        if not audit_log_fn:
            return
        try:
            await _invoke_callback(
                audit_log_fn,
                action,
                outcome,
                actor_email,
                target_email,
                details,
                request=request,
            )
        except Exception:
            # Never block auth flow on audit write errors.
            return

    async def _authenticate(request: Request, email: str, password: str) -> AuthUser | None:
        if authenticate_fn:
            user = await _invoke_callback(authenticate_fn, email, password, request=request)
            if user:
                return user
        if not allow_bootstrap_fallback:
            return None
        return authenticate_bootstrap_user(settings_obj, email=email, password=password)

    def _rate_limit_window_seconds() -> int:
        return max(1, int(_get_setting(settings_obj, "auth_rate_limit_window_seconds", 300)))

    def _rate_limit_max_attempts() -> int:
        return max(0, int(_get_setting(settings_obj, "auth_rate_limit_max_attempts", 10)))

    def _rate_limit_block_seconds() -> int:
        return max(1, int(_get_setting(settings_obj, "auth_rate_limit_block_seconds", 600)))

    def _client_addr(request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
        if forwarded:
            return forwarded
        if request.client and request.client.host:
            return request.client.host
        return "unknown"

    def _login_key(request: Request, email: str) -> str:
        return f"{service_name}:login:{(email or '').strip().lower()}:{_client_addr(request)}"

    def _password_key(request: Request, email: str) -> str:
        return f"{service_name}:password:{(email or '').strip().lower()}:{_client_addr(request)}"

    async def _current_user(request: Request) -> AuthUser | None:
        user = current_user_from_request(request, settings_obj)
        if not user:
            return None
        if not resolve_user_fn:
            return user
        resolved = await _invoke_callback(resolve_user_fn, user.email, request=request)
        return resolved if isinstance(resolved, AuthUser) else None

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

    def _render_login(
        next_path: str,
        csrf_token: str = "",
        error: str | None = None,
        status_code: int = 200,
    ) -> HTMLResponse:
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
      <input type="hidden" name="csrf_token" value="{html.escape(csrf_token)}">
      <label for="email">Email</label>
      <input id="email" name="email" type="email" required autocomplete="username">
      <label for="password">Password</label>
      <input id="password" name="password" type="password" required autocomplete="current-password">
      <button type="submit">Sign in</button>
    </form>
  </div>
</body>
</html>"""
        return HTMLResponse(page, status_code=status_code)

    @router.get("/auth/login")
    async def login_page(request: Request, next: str = home_path):  # noqa: A002
        if not _auth_enabled(settings_obj):
            return RedirectResponse(home_path, status_code=303)
        safe_next = _sanitize_next_path(next, home_path)
        if await _current_user(request):
            return RedirectResponse(safe_next, status_code=303)
        if not _secret(settings_obj):
            return HTMLResponse("Authentication is misconfigured", status_code=503)
        csrf_token = _ensure_csrf_token(request, settings_obj)
        response = _render_login(safe_next, csrf_token=csrf_token)
        _set_csrf_cookie(response, settings_obj, csrf_token)
        return response

    @router.post("/auth/login")
    async def login_submit(request: Request):
        if not _auth_enabled(settings_obj):
            return RedirectResponse(home_path, status_code=303)
        if not _secret(settings_obj):
            return HTMLResponse("Authentication is misconfigured", status_code=503)

        form = await request.form()
        email = str(form.get("email", "")).strip()
        password = str(form.get("password", ""))
        next_path = _sanitize_next_path(str(form.get("next", home_path)), home_path)
        csrf_token = str(form.get("csrf_token", ""))
        email_norm = (email or "").strip().lower()
        if not _valid_csrf(request, settings_obj, csrf_token):
            err_csrf = _ensure_csrf_token(request, settings_obj)
            response = _render_login(
                next_path,
                csrf_token=err_csrf,
                error="Invalid request",
                status_code=400,
            )
            _set_csrf_cookie(response, settings_obj, err_csrf)
            await _audit(
                "login",
                "failure",
                target_email=email_norm or None,
                details={"reason": "invalid_csrf"},
                request=request,
            )
            return response

        login_key = _login_key(request, email)
        now = time.time()
        if limiter.is_blocked(login_key, now):
            err_csrf = _ensure_csrf_token(request, settings_obj)
            response = _render_login(
                next_path,
                csrf_token=err_csrf,
                error="Too many login attempts. Try again later.",
                status_code=429,
            )
            _set_csrf_cookie(response, settings_obj, err_csrf)
            await _audit(
                "login",
                "rate_limited",
                target_email=email_norm or None,
                details={"reason": "too_many_attempts"},
                request=request,
            )
            return response

        user = await _authenticate(request=request, email=email, password=password)
        if not user:
            blocked = limiter.add_failure(
                key=login_key,
                now=now,
                window_seconds=_rate_limit_window_seconds(),
                max_attempts=_rate_limit_max_attempts(),
                block_seconds=_rate_limit_block_seconds(),
            )
            if blocked:
                err_csrf = _ensure_csrf_token(request, settings_obj)
                response = _render_login(
                    next_path,
                    csrf_token=err_csrf,
                    error="Too many login attempts. Try again later.",
                    status_code=429,
                )
                _set_csrf_cookie(response, settings_obj, err_csrf)
                await _audit(
                    "login",
                    "rate_limited",
                    target_email=email_norm or None,
                    details={"reason": "too_many_attempts"},
                    request=request,
                )
                return response
            err_csrf = _ensure_csrf_token(request, settings_obj)
            response = _render_login(
                next_path,
                csrf_token=err_csrf,
                error="Invalid credentials",
            )
            _set_csrf_cookie(response, settings_obj, err_csrf)
            await _audit(
                "login",
                "failure",
                target_email=email_norm or None,
                details={"reason": "invalid_credentials"},
                request=request,
            )
            return response

        limiter.clear(login_key)

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
        _set_csrf_cookie(response, settings_obj, _ensure_csrf_token(request, settings_obj))
        await _audit(
            "login",
            "success",
            actor_email=user.email,
            target_email=user.email,
            details={"next": next_path},
            request=request,
        )
        return response

    @router.get("/auth/invites")
    async def invites_page(request: Request, token: str = "", msg: str = ""):
        if not _auth_enabled(settings_obj):
            return RedirectResponse(home_path, status_code=303)
        if not create_invite_fn or not list_invites_fn:
            return HTMLResponse("Invite flow is not configured", status_code=404)

        user = await _current_user(request)
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

        csrf_token = _ensure_csrf_token(request, settings_obj)

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
      <input type="hidden" name="csrf_token" value="{html.escape(csrf_token)}">
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
  <p><a href="/auth/password">Change my password</a></p>
  <p><a href="{html.escape(home_path)}">Back to app</a></p>
  <p><a href="/auth/users">Manage users</a></p>
</div></body></html>"""
        response = HTMLResponse(page)
        _set_csrf_cookie(response, settings_obj, csrf_token)
        return response

    @router.post("/auth/invites")
    async def create_invite(request: Request):
        if not _auth_enabled(settings_obj):
            return RedirectResponse(home_path, status_code=303)
        if not create_invite_fn:
            return HTMLResponse("Invite flow is not configured", status_code=404)

        user = await _current_user(request)
        if not _can_manage_users(user):
            return RedirectResponse("/auth/login", status_code=303)

        form = await request.form()
        csrf_token = str(form.get("csrf_token", ""))
        if not _valid_csrf(request, settings_obj, csrf_token):
            await _audit(
                "invite_create",
                "failure",
                actor_email=user.email,
                details={"reason": "invalid_csrf"},
                request=request,
            )
            return RedirectResponse("/auth/invites?msg=Invalid+request", status_code=303)

        email = str(form.get("email", "")).strip().lower()
        role = _normalize_role(str(form.get("role", "viewer")))
        if not email:
            await _audit(
                "invite_create",
                "failure",
                actor_email=user.email,
                details={"reason": "email_required"},
                request=request,
            )
            return RedirectResponse("/auth/invites?msg=Email+required", status_code=303)

        token = await _invoke_callback(
            create_invite_fn,
            email,
            role,
            user.email,
            request=request,
        )
        await _audit(
            "invite_create",
            "success",
            actor_email=user.email,
            target_email=email,
            details={"role": role},
            request=request,
        )
        return RedirectResponse(
            f"/auth/invites?msg=Invite+created&token={quote(token or '', safe='')}",
            status_code=303,
        )

    @router.get("/auth/accept")
    async def accept_page(request: Request, token: str = ""):
        if not _auth_enabled(settings_obj):
            return RedirectResponse(home_path, status_code=303)
        if not accept_invite_fn:
            return HTMLResponse("Invite acceptance is not configured", status_code=404)

        csrf_token = _ensure_csrf_token(request, settings_obj)
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
<input type="hidden" name="csrf_token" value="{html.escape(csrf_token)}">
<label for="password">Password</label>
<input id="password" name="password" type="password" required minlength="8" autocomplete="new-password">
<button type="submit">Activate Account</button>
</form></div></body></html>"""
        response = HTMLResponse(page)
        _set_csrf_cookie(response, settings_obj, csrf_token)
        return response

    @router.post("/auth/accept")
    async def accept_submit(request: Request):
        if not _auth_enabled(settings_obj):
            return RedirectResponse(home_path, status_code=303)
        if not accept_invite_fn:
            return HTMLResponse("Invite acceptance is not configured", status_code=404)

        form = await request.form()
        token = str(form.get("token", "")).strip()
        password = str(form.get("password", ""))
        csrf_token = str(form.get("csrf_token", ""))
        if not _valid_csrf(request, settings_obj, csrf_token):
            await _audit(
                "invite_accept",
                "failure",
                details={"reason": "invalid_csrf"},
                request=request,
            )
            return HTMLResponse("Invalid request", status_code=400)
        if not token or len(password) < 8:
            await _audit(
                "invite_accept",
                "failure",
                details={"reason": "invalid_payload"},
                request=request,
            )
            return HTMLResponse("Invalid invite or password too short", status_code=400)

        user = await _invoke_callback(accept_invite_fn, token, password, request=request)
        if not user:
            await _audit(
                "invite_accept",
                "failure",
                details={"reason": "invalid_or_expired_invite"},
                request=request,
            )
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
        _set_csrf_cookie(response, settings_obj, _ensure_csrf_token(request, settings_obj))
        await _audit(
            "invite_accept",
            "success",
            actor_email=user.email,
            target_email=user.email,
            request=request,
        )
        return response

    @router.get("/auth/users")
    async def users_page(request: Request, msg: str = ""):
        if not _auth_enabled(settings_obj):
            return RedirectResponse(home_path, status_code=303)
        if not list_accounts_fn or not update_account_fn:
            return HTMLResponse("User management is not configured", status_code=404)

        user = await _current_user(request)
        if not _can_manage_users(user):
            return RedirectResponse("/auth/login", status_code=303)

        csrf_token = _ensure_csrf_token(request, settings_obj)
        accounts = await _invoke_callback(list_accounts_fn, request=request)
        rows_html = []
        for account in accounts or []:
            email = str(account.get("email", "")).strip().lower()
            role = _normalize_role(str(account.get("role", "viewer")))
            is_active = bool(account.get("is_active", False))
            last_login_at = _fmt_dt(account.get("last_login_at"))
            created_at = _fmt_dt(account.get("created_at"))
            email_safe = html.escape(email)
            role_options = "".join(
                (
                    f"<option value='{role_name}'{' selected' if role_name == role else ''}>"
                    f"{role_name}</option>"
                )
                for role_name in ROLE_ORDER
            )
            status_options = (
                "<option value='true' selected>active</option>"
                "<option value='false'>disabled</option>"
                if is_active
                else "<option value='true'>active</option>"
                "<option value='false' selected>disabled</option>"
            )
            rows_html.append(
                "<tr>"
                f"<td style='padding:.4rem;border-top:1px solid #1f2937;'>{email_safe}</td>"
                "<td style='padding:.4rem;border-top:1px solid #1f2937;'>"
                "<form method='post' action='/auth/users' style='display:flex;gap:.5rem;align-items:center;'>"
                f"<input type='hidden' name='csrf_token' value='{html.escape(csrf_token)}'>"
                f"<input type='hidden' name='email' value='{email_safe}'>"
                f"<select name='role' style='min-width:110px;'>{role_options}</select>"
                f"<select name='is_active' style='min-width:110px;'>{status_options}</select>"
                "<button type='submit'>Save</button>"
                "</form>"
                "</td>"
                f"<td style='padding:.4rem;border-top:1px solid #1f2937;'>{html.escape(last_login_at)}</td>"
                f"<td style='padding:.4rem;border-top:1px solid #1f2937;'>{html.escape(created_at)}</td>"
                "</tr>"
            )
        table_body = "".join(rows_html) or (
            "<tr><td colspan='4' style='padding:.6rem;color:#9ca3af;'>No users found</td></tr>"
        )

        msg_block = ""
        if msg:
            color = "#22c55e" if "updated" in msg.lower() else "#f59e0b"
            msg_block = f"<p style='color:{color};margin:.5rem 0 0 0;'>{html.escape(msg)}</p>"

        page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Manage Users</title>
<style>
body {{ font-family: system-ui, sans-serif; background:#0b1020; color:#e5e7eb; margin:0; }}
.wrap {{ max-width:960px; margin:1.5rem auto; padding:0 1rem; }}
.card {{ background:#111827; border:1px solid #1f2937; border-radius:12px; padding:1rem; margin-bottom:1rem; }}
select {{ width:100%; padding:.45rem .6rem; border-radius:8px; border:1px solid #374151; background:#0f172a; color:#f3f4f6; }}
button {{ padding:.45rem .75rem; border:0; border-radius:8px; background:#2563eb; color:white; font-weight:600; cursor:pointer; }}
table {{ width:100%; border-collapse:collapse; font-size:.92rem; }}
a {{ color:#60a5fa; }}
</style></head><body>
<div class="wrap">
  <div class="card">
    <h1 style="margin:0 0 .25rem 0;">Manage Users</h1>
    <p style="margin:0;color:#9ca3af;">Update roles and account status.</p>
    {msg_block}
  </div>
  <div class="card">
    <table>
      <thead>
        <tr><th align="left">Email</th><th align="left">Role / Status</th><th align="left">Last Login</th><th align="left">Created</th></tr>
      </thead>
      <tbody>{table_body}</tbody>
    </table>
  </div>
  <p><a href="/auth/password">Change my password</a></p>
  <p><a href="/auth/invites">Manage invites</a></p>
  <p><a href="{html.escape(home_path)}">Back to app</a></p>
</div></body></html>"""
        response = HTMLResponse(page)
        _set_csrf_cookie(response, settings_obj, csrf_token)
        return response

    @router.post("/auth/users")
    async def users_update(request: Request):
        if not _auth_enabled(settings_obj):
            return RedirectResponse(home_path, status_code=303)
        if not update_account_fn:
            return HTMLResponse("User management is not configured", status_code=404)

        user = await _current_user(request)
        if not _can_manage_users(user):
            return RedirectResponse("/auth/login", status_code=303)

        form = await request.form()
        csrf_token = str(form.get("csrf_token", ""))
        if not _valid_csrf(request, settings_obj, csrf_token):
            await _audit(
                "user_update",
                "failure",
                actor_email=user.email,
                details={"reason": "invalid_csrf"},
                request=request,
            )
            return RedirectResponse("/auth/users?msg=Invalid+request", status_code=303)

        email = str(form.get("email", "")).strip().lower()
        role = _normalize_role(str(form.get("role", "viewer")))
        is_active_raw = str(form.get("is_active", "true")).strip().lower()
        is_active = is_active_raw in {"1", "true", "yes", "on", "active"}
        if not email:
            await _audit(
                "user_update",
                "failure",
                actor_email=user.email,
                details={"reason": "email_required"},
                request=request,
            )
            return RedirectResponse("/auth/users?msg=Email+required", status_code=303)

        updated = await _invoke_callback(
            update_account_fn,
            email,
            role,
            is_active,
            user.email,
            user.role,
            request=request,
        )
        msg = "User+updated" if updated else "Update+rejected"
        await _audit(
            "user_update",
            "success" if updated else "failure",
            actor_email=user.email,
            target_email=email,
            details={"role": role, "is_active": is_active},
            request=request,
        )
        return RedirectResponse(f"/auth/users?msg={msg}", status_code=303)

    @router.get("/auth/password")
    async def password_page(request: Request, msg: str = ""):
        if not _auth_enabled(settings_obj):
            return RedirectResponse(home_path, status_code=303)
        if not change_password_fn:
            return HTMLResponse("Password change is not configured", status_code=404)

        user = await _current_user(request)
        if not user:
            return RedirectResponse("/auth/login", status_code=303)

        msg_block = ""
        if msg:
            color = "#22c55e" if "updated" in msg.lower() else "#f59e0b"
            msg_block = f"<p style='color:{color};margin:.6rem 0 0 0;'>{html.escape(msg)}</p>"

        csrf_token = _ensure_csrf_token(request, settings_obj)

        page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Change Password</title>
<style>
body {{ font-family: system-ui, sans-serif; background:#0b1020; color:#e5e7eb; margin:0; }}
.wrap {{ min-height:100vh; display:flex; align-items:center; justify-content:center; padding:1rem; }}
.card {{ width:100%; max-width:460px; background:#111827; border:1px solid #1f2937; border-radius:12px; padding:1.25rem; }}
label {{ display:block; margin:.75rem 0 .25rem 0; font-size:.9rem; }}
input {{ width:100%; padding:.6rem .7rem; border-radius:8px; border:1px solid #374151; background:#0f172a; color:#f3f4f6; }}
button {{ margin-top:1rem; width:100%; padding:.65rem .8rem; border:0; border-radius:8px; background:#2563eb; color:#fff; font-weight:600; cursor:pointer; }}
a {{ color:#60a5fa; }}
</style></head><body>
  <div class="wrap">
    <form method="post" class="card">
      <h1 style="margin:0 0 .25rem 0;">Change Password</h1>
      <p style="margin:0;color:#9ca3af;">Signed in as {html.escape(user.email)}</p>
      {msg_block}
      <input type="hidden" name="csrf_token" value="{html.escape(csrf_token)}">
      <label for="current_password">Current password</label>
      <input id="current_password" name="current_password" type="password" required autocomplete="current-password">
      <label for="new_password">New password</label>
      <input id="new_password" name="new_password" type="password" required minlength="8" autocomplete="new-password">
      <label for="confirm_password">Confirm new password</label>
      <input id="confirm_password" name="confirm_password" type="password" required minlength="8" autocomplete="new-password">
      <button type="submit">Update Password</button>
      <p style="margin:.9rem 0 0 0;"><a href="{html.escape(home_path)}">Back to app</a></p>
    </form>
  </div>
</body></html>"""
        response = HTMLResponse(page)
        _set_csrf_cookie(response, settings_obj, csrf_token)
        return response

    @router.post("/auth/password")
    async def password_submit(request: Request):
        if not _auth_enabled(settings_obj):
            return RedirectResponse(home_path, status_code=303)
        if not change_password_fn:
            return HTMLResponse("Password change is not configured", status_code=404)

        user = await _current_user(request)
        if not user:
            return RedirectResponse("/auth/login", status_code=303)

        form = await request.form()
        csrf_token = str(form.get("csrf_token", ""))
        if not _valid_csrf(request, settings_obj, csrf_token):
            await _audit(
                "password_change",
                "failure",
                actor_email=user.email,
                target_email=user.email,
                details={"reason": "invalid_csrf"},
                request=request,
            )
            return RedirectResponse("/auth/password?msg=Invalid+request", status_code=303)

        current_password = str(form.get("current_password", ""))
        new_password = str(form.get("new_password", ""))
        confirm_password = str(form.get("confirm_password", ""))
        pwd_key = _password_key(request, user.email)
        now = time.time()
        if limiter.is_blocked(pwd_key, now):
            await _audit(
                "password_change",
                "rate_limited",
                actor_email=user.email,
                target_email=user.email,
                details={"reason": "too_many_attempts"},
                request=request,
            )
            return RedirectResponse("/auth/password?msg=Too+many+attempts", status_code=303)

        if len(new_password) < 8:
            await _audit(
                "password_change",
                "failure",
                actor_email=user.email,
                target_email=user.email,
                details={"reason": "password_too_short"},
                request=request,
            )
            return RedirectResponse("/auth/password?msg=Password+too+short", status_code=303)
        if new_password != confirm_password:
            await _audit(
                "password_change",
                "failure",
                actor_email=user.email,
                target_email=user.email,
                details={"reason": "password_mismatch"},
                request=request,
            )
            return RedirectResponse("/auth/password?msg=Passwords+do+not+match", status_code=303)

        changed = await _invoke_callback(
            change_password_fn,
            user.email,
            current_password,
            new_password,
            request=request,
        )
        if not changed:
            limiter.add_failure(
                key=pwd_key,
                now=now,
                window_seconds=_rate_limit_window_seconds(),
                max_attempts=_rate_limit_max_attempts(),
                block_seconds=_rate_limit_block_seconds(),
            )
            await _audit(
                "password_change",
                "failure",
                actor_email=user.email,
                target_email=user.email,
                details={"reason": "current_password_invalid"},
                request=request,
            )
            return RedirectResponse("/auth/password?msg=Current+password+invalid", status_code=303)

        limiter.clear(pwd_key)
        await _audit(
            "password_change",
            "success",
            actor_email=user.email,
            target_email=user.email,
            request=request,
        )
        return RedirectResponse("/auth/password?msg=Password+updated", status_code=303)

    @router.post("/auth/logout")
    async def logout_post():
        response = RedirectResponse("/auth/login", status_code=303)
        response.delete_cookie(_cookie_name(settings_obj), path="/")
        response.delete_cookie(_csrf_cookie_name(settings_obj), path="/")
        return response

    @router.get("/auth/logout")
    async def logout_get():
        response = RedirectResponse("/auth/login", status_code=303)
        response.delete_cookie(_cookie_name(settings_obj), path="/")
        response.delete_cookie(_csrf_cookie_name(settings_obj), path="/")
        return response

    return router
