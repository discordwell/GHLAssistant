"""Import campaigns from GHL."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.campaign import Campaign, CampaignStep
from ..models.location import Location
from ..schemas.sync import SyncResult


async def import_campaigns(
    db: AsyncSession, location: Location, campaigns_data: list[dict],
) -> SyncResult:
    """Import campaigns and steps from GHL."""
    result = SyncResult()

    for c_data in campaigns_data:
        ghl_id = c_data.get("id", c_data.get("_id", ""))
        name = c_data.get("name", "")
        if not name:
            continue

        stmt = select(Campaign).where(
            Campaign.location_id == location.id, Campaign.ghl_id == ghl_id
        )
        campaign = (await db.execute(stmt)).scalar_one_or_none()

        status = c_data.get("status", "draft")

        if campaign:
            campaign.name = name
            campaign.status = status
            campaign.last_synced_at = datetime.now(timezone.utc)
            result.updated += 1
        else:
            campaign = Campaign(
                location_id=location.id, name=name, status=status,
                ghl_id=ghl_id, ghl_location_id=location.ghl_location_id,
                last_synced_at=datetime.now(timezone.utc),
            )
            db.add(campaign)
            await db.flush()
            result.created += 1

    await db.commit()
    return result
