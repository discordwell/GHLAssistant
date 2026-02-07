"""FastAPI dependencies for tenant resolution."""

from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.location import Location


async def get_current_location(
    slug: str = Path(..., description="Location slug"),
    db: AsyncSession = Depends(get_db),
) -> Location:
    """Resolve location slug to Location model. Raises 404 if not found."""
    result = await db.execute(select(Location).where(Location.slug == slug))
    location = result.scalar_one_or_none()
    if not location:
        raise HTTPException(status_code=404, detail=f"Location '{slug}' not found")
    return location


async def get_location_id(
    location: Location = Depends(get_current_location),
) -> uuid.UUID:
    """Shorthand dependency that returns just the location_id."""
    return location.id
