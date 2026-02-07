"""GHL -> local CRM importer."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.contact import Contact
from ..models.tag import Tag, ContactTag
from ..models.custom_field import CustomFieldDefinition, CustomFieldValue
from ..models.custom_value import CustomValue
from ..models.pipeline import Pipeline, PipelineStage
from ..models.opportunity import Opportunity
from ..models.location import Location
from ..schemas.sync import SyncResult
from .field_mapper import ghl_contact_to_local, ghl_opportunity_to_local


async def import_tags(
    db: AsyncSession, location: Location, tags_data: list[dict]
) -> SyncResult:
    """Import tags from GHL."""
    result = SyncResult()
    for item in tags_data:
        ghl_id = item.get("id", item.get("_id", ""))
        name = item.get("name", "")
        if not name:
            continue

        # Check for existing by ghl_id
        stmt = select(Tag).where(Tag.location_id == location.id, Tag.ghl_id == ghl_id)
        existing = (await db.execute(stmt)).scalar_one_or_none()

        if existing:
            existing.name = name
            result.updated += 1
        else:
            # Check by name
            stmt = select(Tag).where(Tag.location_id == location.id, Tag.name == name)
            by_name = (await db.execute(stmt)).scalar_one_or_none()
            if by_name:
                by_name.ghl_id = ghl_id
                by_name.ghl_location_id = location.ghl_location_id
                by_name.last_synced_at = datetime.now(timezone.utc)
                result.updated += 1
            else:
                tag = Tag(
                    location_id=location.id, name=name,
                    ghl_id=ghl_id, ghl_location_id=location.ghl_location_id,
                    last_synced_at=datetime.now(timezone.utc),
                )
                db.add(tag)
                result.created += 1

    await db.commit()
    return result


async def import_custom_fields(
    db: AsyncSession, location: Location, fields_data: list[dict]
) -> SyncResult:
    """Import custom field definitions from GHL."""
    result = SyncResult()
    for item in fields_data:
        ghl_id = item.get("id", item.get("_id", ""))
        name = item.get("name", "")
        field_key = item.get("fieldKey", "")
        data_type = item.get("dataType", "TEXT").lower()

        if not name:
            continue

        stmt = select(CustomFieldDefinition).where(
            CustomFieldDefinition.location_id == location.id,
            CustomFieldDefinition.ghl_id == ghl_id,
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()

        if existing:
            existing.name = name
            existing.field_key = field_key
            existing.data_type = data_type
            result.updated += 1
        else:
            defn = CustomFieldDefinition(
                location_id=location.id, name=name, field_key=field_key,
                data_type=data_type, ghl_id=ghl_id,
                ghl_location_id=location.ghl_location_id,
                last_synced_at=datetime.now(timezone.utc),
            )
            db.add(defn)
            result.created += 1

    await db.commit()
    return result


async def import_custom_values(
    db: AsyncSession, location: Location, values_data: list[dict]
) -> SyncResult:
    """Import custom values from GHL."""
    result = SyncResult()
    for item in values_data:
        ghl_id = item.get("id", item.get("_id", ""))
        name = item.get("name", "")
        value = item.get("value", "")

        if not name:
            continue

        stmt = select(CustomValue).where(
            CustomValue.location_id == location.id, CustomValue.ghl_id == ghl_id
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()

        if existing:
            existing.name = name
            existing.value = value
            result.updated += 1
        else:
            cv = CustomValue(
                location_id=location.id, name=name, value=value,
                ghl_id=ghl_id, ghl_location_id=location.ghl_location_id,
                last_synced_at=datetime.now(timezone.utc),
            )
            db.add(cv)
            result.created += 1

    await db.commit()
    return result


async def import_pipelines(
    db: AsyncSession, location: Location, pipelines_data: list[dict]
) -> tuple[SyncResult, dict[str, uuid.UUID]]:
    """Import pipelines and stages. Returns (result, stage_ghl_id_map)."""
    result = SyncResult()
    stage_map: dict[str, uuid.UUID] = {}  # ghl_stage_id -> local stage UUID

    for p_data in pipelines_data:
        ghl_id = p_data.get("id", p_data.get("_id", ""))
        name = p_data.get("name", "")

        if not name:
            continue

        stmt = select(Pipeline).where(
            Pipeline.location_id == location.id, Pipeline.ghl_id == ghl_id
        )
        pipeline = (await db.execute(stmt)).scalar_one_or_none()

        if pipeline:
            pipeline.name = name
            result.updated += 1
        else:
            pipeline = Pipeline(
                location_id=location.id, name=name,
                ghl_id=ghl_id, ghl_location_id=location.ghl_location_id,
                last_synced_at=datetime.now(timezone.utc),
            )
            db.add(pipeline)
            await db.flush()
            result.created += 1

        # Import stages
        for i, s_data in enumerate(p_data.get("stages", [])):
            s_ghl_id = s_data.get("id", s_data.get("_id", ""))
            s_name = s_data.get("name", "")

            stmt = select(PipelineStage).where(
                PipelineStage.pipeline_id == pipeline.id,
                PipelineStage.ghl_id == s_ghl_id,
            )
            stage = (await db.execute(stmt)).scalar_one_or_none()

            if stage:
                stage.name = s_name
                stage.position = i
            else:
                stage = PipelineStage(
                    pipeline_id=pipeline.id, name=s_name, position=i,
                    ghl_id=s_ghl_id, ghl_location_id=location.ghl_location_id,
                    last_synced_at=datetime.now(timezone.utc),
                )
                db.add(stage)
                await db.flush()

            stage_map[s_ghl_id] = stage.id

    await db.commit()
    return result, stage_map


async def import_contacts(
    db: AsyncSession, location: Location, contacts_data: list[dict]
) -> tuple[SyncResult, dict[str, uuid.UUID]]:
    """Import contacts from GHL. Returns (result, contact_ghl_id_map)."""
    result = SyncResult()
    contact_map: dict[str, uuid.UUID] = {}

    for c_data in contacts_data:
        ghl_id = c_data.get("id", c_data.get("_id", ""))
        fields = ghl_contact_to_local(c_data)

        if not fields:
            result.skipped += 1
            continue

        # Dedup: first by ghl_id, then by email
        stmt = select(Contact).where(
            Contact.location_id == location.id, Contact.ghl_id == ghl_id
        )
        contact = (await db.execute(stmt)).scalar_one_or_none()

        if not contact and fields.get("email"):
            stmt = select(Contact).where(
                Contact.location_id == location.id,
                Contact.email == fields["email"],
            )
            contact = (await db.execute(stmt)).scalar_one_or_none()

        if contact:
            for k, v in fields.items():
                setattr(contact, k, v)
            contact.ghl_id = ghl_id
            contact.last_synced_at = datetime.now(timezone.utc)
            result.updated += 1
        else:
            contact = Contact(
                location_id=location.id,
                ghl_id=ghl_id,
                ghl_location_id=location.ghl_location_id,
                last_synced_at=datetime.now(timezone.utc),
                **fields,
            )
            db.add(contact)
            await db.flush()
            result.created += 1

        contact_map[ghl_id] = contact.id

        # Import contact tags
        for tag_name in c_data.get("tags", []):
            stmt = select(Tag).where(
                Tag.location_id == location.id, Tag.name == tag_name
            )
            tag = (await db.execute(stmt)).scalar_one_or_none()
            if tag:
                ct_stmt = select(ContactTag).where(
                    ContactTag.contact_id == contact.id,
                    ContactTag.tag_id == tag.id,
                )
                if not (await db.execute(ct_stmt)).scalar_one_or_none():
                    db.add(ContactTag(contact_id=contact.id, tag_id=tag.id))

    await db.commit()
    return result, contact_map


async def import_opportunities(
    db: AsyncSession,
    location: Location,
    opps_data: list[dict],
    stage_map: dict[str, uuid.UUID],
    contact_map: dict[str, uuid.UUID],
    pipeline_ghl_id: str,
) -> SyncResult:
    """Import opportunities for a pipeline."""
    result = SyncResult()

    # Resolve pipeline
    stmt = select(Pipeline).where(
        Pipeline.location_id == location.id, Pipeline.ghl_id == pipeline_ghl_id
    )
    pipeline = (await db.execute(stmt)).scalar_one_or_none()
    if not pipeline:
        result.errors.append(f"Pipeline {pipeline_ghl_id} not found locally")
        return result

    for o_data in opps_data:
        ghl_id = o_data.get("id", o_data.get("_id", ""))
        fields = ghl_opportunity_to_local(o_data)

        # Map stage
        ghl_stage_id = o_data.get("pipelineStageId", "")
        stage_id = stage_map.get(ghl_stage_id)

        # Map contact
        ghl_contact_id = o_data.get("contactId", "")
        contact_id = contact_map.get(ghl_contact_id)

        stmt = select(Opportunity).where(
            Opportunity.location_id == location.id, Opportunity.ghl_id == ghl_id
        )
        opp = (await db.execute(stmt)).scalar_one_or_none()

        if opp:
            for k, v in fields.items():
                setattr(opp, k, v)
            if stage_id:
                opp.stage_id = stage_id
            if contact_id:
                opp.contact_id = contact_id
            opp.last_synced_at = datetime.now(timezone.utc)
            result.updated += 1
        else:
            opp = Opportunity(
                location_id=location.id,
                pipeline_id=pipeline.id,
                stage_id=stage_id,
                contact_id=contact_id,
                ghl_id=ghl_id,
                ghl_location_id=location.ghl_location_id,
                last_synced_at=datetime.now(timezone.utc),
                **fields,
            )
            db.add(opp)
            result.created += 1

    await db.commit()
    return result
