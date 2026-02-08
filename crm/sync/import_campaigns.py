"""Import campaigns from GHL."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.campaign import Campaign, CampaignStep
from ..models.location import Location
from ..schemas.sync import SyncResult


def _to_dict(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    return {}


def _extract_campaign_payload(detail: dict) -> dict:
    if not detail:
        return {}
    if isinstance(detail.get("campaign"), dict):
        return detail["campaign"]
    return detail


def _extract_steps(campaign_payload: dict, list_payload: dict) -> list[dict]:
    for source in (campaign_payload, list_payload):
        src = _to_dict(source)
        for key in ("steps", "campaignSteps", "actions"):
            value = src.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _delay_to_minutes(step_data: dict) -> int:
    raw = step_data.get("delayMinutes", step_data.get("delayInMinutes"))
    if isinstance(raw, (int, float)):
        return max(int(raw), 0)

    delay = step_data.get("delay")
    if not isinstance(delay, dict):
        return 0

    value = delay.get("value", 0)
    if not isinstance(value, (int, float)):
        return 0

    unit = str(delay.get("unit", "minutes")).lower()
    if unit.startswith("hour"):
        return max(int(value * 60), 0)
    if unit.startswith("day"):
        return max(int(value * 60 * 24), 0)
    return max(int(value), 0)


async def import_campaigns(
    db: AsyncSession, location: Location, campaigns_data: list[dict],
    details_by_campaign: dict[str, dict] | None = None,
) -> SyncResult:
    """Import campaigns and steps from GHL."""
    result = SyncResult()
    details_by_campaign = details_by_campaign or {}

    for c_data in campaigns_data:
        ghl_id = c_data.get("id", c_data.get("_id", ""))
        name = c_data.get("name", "")
        if not name:
            continue

        detail_payload = _extract_campaign_payload(_to_dict(details_by_campaign.get(ghl_id)))
        description = detail_payload.get("description", c_data.get("description"))
        stmt = select(Campaign).where(
            Campaign.location_id == location.id, Campaign.ghl_id == ghl_id
        )
        campaign = (await db.execute(stmt)).scalar_one_or_none()

        status = detail_payload.get("status", c_data.get("status", "draft"))

        if campaign:
            campaign.name = name
            campaign.description = description
            campaign.status = status
            campaign.last_synced_at = datetime.now(timezone.utc)
            result.updated += 1
        else:
            campaign = Campaign(
                location_id=location.id, name=name, description=description, status=status,
                ghl_id=ghl_id, ghl_location_id=location.ghl_location_id,
                last_synced_at=datetime.now(timezone.utc),
            )
            db.add(campaign)
            await db.flush()
            result.created += 1

        # Import/update campaign steps
        steps = _extract_steps(detail_payload, _to_dict(c_data))
        for i, step_data in enumerate(steps):
            step_type = str(
                step_data.get("stepType", step_data.get("type", step_data.get("channel", "sms")))
            ).lower()
            subject = step_data.get("subject", step_data.get("title"))
            body = step_data.get("body", step_data.get("message", step_data.get("content")))
            delay_minutes = _delay_to_minutes(step_data)

            stmt = select(CampaignStep).where(
                CampaignStep.campaign_id == campaign.id,
                CampaignStep.position == i,
            )
            step = (await db.execute(stmt)).scalar_one_or_none()

            if step:
                step.step_type = step_type
                step.subject = subject
                step.body = body
                step.delay_minutes = delay_minutes
            else:
                step = CampaignStep(
                    campaign_id=campaign.id,
                    step_type=step_type,
                    position=i,
                    subject=subject,
                    body=body,
                    delay_minutes=delay_minutes,
                )
                db.add(step)

    await db.commit()
    return result
