"""Tenant context middleware (optional - mostly handled by deps)."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class TenantMiddleware(BaseHTTPMiddleware):
    """Extracts location slug from URL path and sets it on request state."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # Extract slug from /loc/{slug}/... pattern
        if path.startswith("/loc/"):
            parts = path.split("/")
            if len(parts) >= 3:
                request.state.location_slug = parts[2]
        response = await call_next(request)
        return response
