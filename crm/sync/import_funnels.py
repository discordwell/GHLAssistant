"""Import funnels and pages from GHL."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.funnel import Funnel, FunnelPage
from ..models.location import Location
from ..schemas.sync import SyncResult


async def import_funnels(
    db: AsyncSession, location: Location, funnels_data: list[dict],
    pages_by_funnel: dict[str, list[dict]] | None = None,
) -> SyncResult:
    """Import funnels and pages from GHL."""
    result = SyncResult()
    pages_by_funnel = pages_by_funnel or {}

    for f_data in funnels_data:
        ghl_id = f_data.get("id", f_data.get("_id", ""))
        name = f_data.get("name", "")
        if not name:
            continue

        stmt = select(Funnel).where(
            Funnel.location_id == location.id, Funnel.ghl_id == ghl_id
        )
        funnel = (await db.execute(stmt)).scalar_one_or_none()

        if funnel:
            funnel.name = name
            funnel.last_synced_at = datetime.now(timezone.utc)
            result.updated += 1
        else:
            funnel = Funnel(
                location_id=location.id, name=name,
                ghl_id=ghl_id, ghl_location_id=location.ghl_location_id,
                last_synced_at=datetime.now(timezone.utc),
            )
            db.add(funnel)
            await db.flush()
            result.created += 1

        # Import pages
        for i, p_data in enumerate(pages_by_funnel.get(ghl_id, [])):
            p_ghl_id = p_data.get("id", p_data.get("_id", ""))
            p_name = p_data.get("name", f"Page {i+1}")
            slug = p_data.get("slug", p_data.get("path", f"page-{i+1}"))

            if p_ghl_id:
                stmt = select(FunnelPage).where(
                    FunnelPage.funnel_id == funnel.id, FunnelPage.ghl_id == p_ghl_id
                )
                page = (await db.execute(stmt)).scalar_one_or_none()
            else:
                page = None

            if page:
                page.name = p_name
                page.url_slug = slug
            else:
                page = FunnelPage(
                    funnel_id=funnel.id,
                    name=p_name,
                    url_slug=slug,
                    content_html=p_data.get("html", ""),
                    position=i,
                    ghl_id=p_ghl_id,
                )
                db.add(page)

    await db.commit()
    return result
