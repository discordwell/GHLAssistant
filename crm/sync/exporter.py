"""Local CRM -> GHL exporter."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.contact import Contact
from ..models.tag import Tag
from ..models.pipeline import Pipeline, PipelineStage
from ..models.opportunity import Opportunity
from ..models.location import Location
from ..schemas.sync import SyncResult
from .field_mapper import local_contact_to_ghl, local_opportunity_to_ghl


async def export_tags(db: AsyncSession, location: Location, ghl) -> SyncResult:
    """Export local tags to GHL."""
    result = SyncResult()
    stmt = select(Tag).where(Tag.location_id == location.id)
    tags = list((await db.execute(stmt)).scalars().all())

    for tag in tags:
        try:
            if tag.ghl_id:
                # Tag exists in GHL, skip (GHL tags are name-based, no update needed)
                result.skipped += 1
            else:
                resp = await ghl.tags.create(
                    name=tag.name, location_id=location.ghl_location_id
                )
                tag.ghl_id = resp.get("tag", {}).get("id", resp.get("id", ""))
                tag.last_synced_at = datetime.now(timezone.utc)
                result.created += 1
        except Exception as e:
            result.errors.append(f"Tag '{tag.name}': {e}")

    await db.commit()
    return result


async def export_contacts(db: AsyncSession, location: Location, ghl) -> SyncResult:
    """Export local contacts to GHL."""
    result = SyncResult()
    stmt = select(Contact).where(Contact.location_id == location.id)
    contacts = list((await db.execute(stmt)).scalars().all())

    for contact in contacts:
        ghl_data = local_contact_to_ghl(contact)
        ghl_data["locationId"] = location.ghl_location_id

        try:
            if contact.ghl_id:
                await ghl.contacts.update(contact.ghl_id, **ghl_data)
                result.updated += 1
            else:
                resp = await ghl.contacts.create(**ghl_data)
                contact_resp = resp.get("contact", resp)
                contact.ghl_id = contact_resp.get("id", "")
                result.created += 1

            contact.last_synced_at = datetime.now(timezone.utc)
        except Exception as e:
            result.errors.append(f"Contact '{contact.full_name}': {e}")

    await db.commit()
    return result


async def export_pipelines(db: AsyncSession, location: Location, ghl) -> SyncResult:
    """Export local pipelines to GHL (read-only in GHL API - just log)."""
    result = SyncResult()
    # GHL pipeline API is typically read-only for creation via API
    # We map stages by name during opportunity export
    stmt = select(Pipeline).where(Pipeline.location_id == location.id)
    pipelines = list((await db.execute(stmt)).scalars().all())
    result.skipped = len(pipelines)
    return result


async def export_opportunities(db: AsyncSession, location: Location, ghl) -> SyncResult:
    """Export local opportunities to GHL."""
    result = SyncResult()
    stmt = (
        select(Opportunity)
        .where(Opportunity.location_id == location.id)
        .options(selectinload(Opportunity.stage), selectinload(Opportunity.pipeline), selectinload(Opportunity.contact))
    )
    opps = list((await db.execute(stmt)).scalars().all())

    for opp in opps:
        ghl_data = local_opportunity_to_ghl(opp)

        # Map pipeline and stage by ghl_id
        if opp.pipeline and opp.pipeline.ghl_id:
            ghl_data["pipelineId"] = opp.pipeline.ghl_id
        if opp.stage and opp.stage.ghl_id:
            ghl_data["pipelineStageId"] = opp.stage.ghl_id

        if opp.contact and opp.contact.ghl_id:
            ghl_data["contactId"] = opp.contact.ghl_id

        ghl_data["locationId"] = location.ghl_location_id

        try:
            if opp.ghl_id:
                await ghl.opportunities.update(opp.ghl_id, **ghl_data)
                result.updated += 1
            else:
                if "pipelineId" not in ghl_data or "pipelineStageId" not in ghl_data:
                    result.errors.append(
                        f"Opportunity '{opp.name}': missing GHL pipeline/stage mapping"
                    )
                    continue
                resp = await ghl.opportunities.create(**ghl_data)
                opp_resp = resp.get("opportunity", resp)
                opp.ghl_id = opp_resp.get("id", "")
                result.created += 1

            opp.last_synced_at = datetime.now(timezone.utc)
        except Exception as e:
            result.errors.append(f"Opportunity '{opp.name}': {e}")

    await db.commit()
    return result
