"""Campaign service - CRUD campaigns, steps, enrollments, triggering."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.campaign import Campaign, CampaignStep, CampaignEnrollment


async def list_campaigns(
    db: AsyncSession, location_id: uuid.UUID
) -> list[Campaign]:
    stmt = (
        select(Campaign)
        .where(Campaign.location_id == location_id)
        .options(selectinload(Campaign.steps), selectinload(Campaign.enrollments))
        .order_by(Campaign.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_campaign(db: AsyncSession, campaign_id: uuid.UUID) -> Campaign | None:
    stmt = (
        select(Campaign)
        .where(Campaign.id == campaign_id)
        .options(
            selectinload(Campaign.steps),
            selectinload(Campaign.enrollments).selectinload(CampaignEnrollment.contact),
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_campaign(
    db: AsyncSession, location_id: uuid.UUID, **kwargs
) -> Campaign:
    campaign = Campaign(location_id=location_id, **kwargs)
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    return campaign


async def update_campaign(
    db: AsyncSession, campaign_id: uuid.UUID, **kwargs
) -> Campaign | None:
    stmt = select(Campaign).where(Campaign.id == campaign_id)
    campaign = (await db.execute(stmt)).scalar_one_or_none()
    if not campaign:
        return None
    for k, v in kwargs.items():
        setattr(campaign, k, v)
    await db.commit()
    await db.refresh(campaign)
    return campaign


async def delete_campaign(db: AsyncSession, campaign_id: uuid.UUID) -> bool:
    stmt = select(Campaign).where(Campaign.id == campaign_id)
    campaign = (await db.execute(stmt)).scalar_one_or_none()
    if not campaign:
        return False
    await db.delete(campaign)
    await db.commit()
    return True


async def add_step(
    db: AsyncSession, campaign_id: uuid.UUID, **kwargs
) -> CampaignStep:
    stmt = select(func.max(CampaignStep.position)).where(
        CampaignStep.campaign_id == campaign_id
    )
    result = (await db.execute(stmt)).scalar()
    max_pos = result if result is not None else -1
    step = CampaignStep(campaign_id=campaign_id, position=max_pos + 1, **kwargs)
    db.add(step)
    await db.commit()
    await db.refresh(step)
    return step


async def update_step(
    db: AsyncSession, step_id: uuid.UUID, **kwargs
) -> CampaignStep | None:
    stmt = select(CampaignStep).where(CampaignStep.id == step_id)
    step = (await db.execute(stmt)).scalar_one_or_none()
    if not step:
        return None
    for k, v in kwargs.items():
        setattr(step, k, v)
    await db.commit()
    await db.refresh(step)
    return step


async def delete_step(db: AsyncSession, step_id: uuid.UUID) -> bool:
    stmt = select(CampaignStep).where(CampaignStep.id == step_id)
    step = (await db.execute(stmt)).scalar_one_or_none()
    if not step:
        return False
    await db.delete(step)
    await db.commit()
    return True


async def enroll_contact(
    db: AsyncSession, location_id: uuid.UUID, campaign_id: uuid.UUID, contact_id: uuid.UUID,
) -> CampaignEnrollment | None:
    """Enroll a contact. Returns None if already enrolled."""
    stmt = select(CampaignEnrollment).where(
        CampaignEnrollment.campaign_id == campaign_id,
        CampaignEnrollment.contact_id == contact_id,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        return None
    enrollment = CampaignEnrollment(
        location_id=location_id,
        campaign_id=campaign_id,
        contact_id=contact_id,
    )
    db.add(enrollment)
    await db.commit()
    await db.refresh(enrollment)
    return enrollment


async def unenroll_contact(
    db: AsyncSession, enrollment_id: uuid.UUID,
) -> bool:
    stmt = select(CampaignEnrollment).where(CampaignEnrollment.id == enrollment_id)
    enrollment = (await db.execute(stmt)).scalar_one_or_none()
    if not enrollment:
        return False
    await db.delete(enrollment)
    await db.commit()
    return True


async def trigger_next_step(
    db: AsyncSession, campaign_id: uuid.UUID,
) -> dict:
    """Advance all active enrollments to next step. Returns summary."""
    campaign = await get_campaign(db, campaign_id)
    if not campaign:
        return {"error": "Campaign not found"}

    steps = sorted(campaign.steps, key=lambda s: s.position)
    if not steps:
        return {"error": "No steps configured"}

    advanced = 0
    completed = 0
    for enrollment in campaign.enrollments:
        if enrollment.status != "active":
            continue
        if enrollment.current_step < len(steps):
            enrollment.current_step += 1
            advanced += 1
            if enrollment.current_step >= len(steps):
                enrollment.status = "completed"
                enrollment.completed_at = datetime.now(timezone.utc)
                completed += 1

    await db.commit()
    return {"advanced": advanced, "completed": completed}
