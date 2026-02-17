"""FastAPI dependencies for tenant resolution."""

from __future__ import annotations

import hmac
import uuid

from fastapi import Depends, HTTPException, Path, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..models.location import Location


async def get_current_location(
    request: Request,
    slug: str = Path(..., description="Location slug"),
    db: AsyncSession = Depends(get_db),
) -> Location:
    """Resolve location slug to Location model. Raises 404 if not found."""
    result = await db.execute(select(Location).where(Location.slug == slug))
    location = result.scalar_one_or_none()
    if not location:
        raise HTTPException(status_code=404, detail=f"Location '{slug}' not found")

    configured_tokens = settings.tenant_access_tokens_map
    expected_token = configured_tokens.get(slug)
    provided_token = (
        request.headers.get(settings.tenant_token_header, "").strip()
        or request.headers.get("x-location-token", "").strip()
    )

    if expected_token:
        if not provided_token or not hmac.compare_digest(provided_token, expected_token):
            raise HTTPException(status_code=403, detail="Location access token required")
    elif settings.tenant_auth_required:
        raise HTTPException(status_code=403, detail="Tenant authorization required")

    return location


async def get_location_id(
    location: Location = Depends(get_current_location),
) -> uuid.UUID:
    """Shorthand dependency that returns just the location_id."""
    return location.id
