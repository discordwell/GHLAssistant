"""GHL -> local CRM importer."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

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
from .raw_store import upsert_raw_entity


def _iter_custom_fields(payload: Any) -> list[dict[str, Any]]:
    """Normalize GHL customFields payload to a list of dict items."""
    if not payload:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        # Some APIs represent custom fields as a dict keyed by field key or id.
        items: list[dict[str, Any]] = []
        for key, value in payload.items():
            if not isinstance(key, str) or not key:
                continue
            items.append({"fieldKey": key, "value": value})
        return items
    return []


def _extract_custom_field_identifier(item: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return (ghl_definition_id, field_key) from a custom field value item."""
    raw_id = item.get("id") or item.get("_id") or item.get("customFieldId") or item.get("fieldId")
    ghl_id = raw_id if isinstance(raw_id, str) and raw_id else None

    raw_key = item.get("fieldKey") or item.get("key") or item.get("field_key")
    field_key = raw_key if isinstance(raw_key, str) and raw_key else None

    return ghl_id, field_key


def _extract_custom_field_value(item: dict[str, Any]) -> Any:
    for key in ("value", "fieldValue", "field_value", "valueText", "valueNumber", "valueDate", "valueBool"):
        if key in item:
            return item.get(key)
    # Some shapes use {id: ..., ...} with a single remaining non-id key.
    return item.get("val")


def _apply_custom_field_value(
    cfv: CustomFieldValue,
    *,
    data_type: str | None,
    raw_value: Any,
) -> None:
    """Set typed value columns on CustomFieldValue, clearing other columns."""
    cfv.value_text = None
    cfv.value_number = None
    cfv.value_date = None
    cfv.value_bool = None

    if raw_value is None:
        return

    dt = (data_type or "").strip().lower()

    if dt in {"number", "numeric", "float", "decimal", "integer"}:
        try:
            cfv.value_number = float(raw_value)
            return
        except (TypeError, ValueError):
            pass

    if dt in {"date", "datetime"}:
        # Preserve as-is (GHL often returns ISO strings).
        cfv.value_date = str(raw_value)
        return

    if dt in {"checkbox", "boolean", "bool"}:
        if isinstance(raw_value, bool):
            cfv.value_bool = raw_value
            return
        if isinstance(raw_value, (int, float)):
            cfv.value_bool = bool(raw_value)
            return
        if isinstance(raw_value, str):
            normalized = raw_value.strip().lower()
            if normalized in {"true", "1", "yes", "y", "on", "active"}:
                cfv.value_bool = True
                return
            if normalized in {"false", "0", "no", "n", "off", "inactive"}:
                cfv.value_bool = False
                return

    # Default: store as text (JSON when structured).
    if isinstance(raw_value, str):
        cfv.value_text = raw_value
    else:
        cfv.value_text = json.dumps(raw_value, ensure_ascii=False, default=str)


async def _load_custom_field_def_maps(
    db: AsyncSession,
    *,
    location_id: uuid.UUID,
    entity_type: str,
) -> tuple[dict[str, CustomFieldDefinition], dict[str, CustomFieldDefinition]]:
    stmt = select(CustomFieldDefinition).where(
        CustomFieldDefinition.location_id == location_id,
        CustomFieldDefinition.entity_type == entity_type,
    )
    defs = list((await db.execute(stmt)).scalars().all())

    by_ghl_id: dict[str, CustomFieldDefinition] = {
        d.ghl_id: d for d in defs if isinstance(d.ghl_id, str) and d.ghl_id
    }
    by_field_key: dict[str, CustomFieldDefinition] = {
        d.field_key: d for d in defs if isinstance(d.field_key, str) and d.field_key
    }
    return by_ghl_id, by_field_key


async def _upsert_custom_field_values(
    db: AsyncSession,
    *,
    entity_id: uuid.UUID,
    entity_type: str,
    custom_fields_payload: Any,
    defs_by_ghl_id: dict[str, CustomFieldDefinition],
    defs_by_field_key: dict[str, CustomFieldDefinition],
) -> None:
    items = _iter_custom_fields(custom_fields_payload)
    if not items:
        return

    for item in items:
        ghl_def_id, field_key = _extract_custom_field_identifier(item)
        defn = None
        if ghl_def_id and ghl_def_id in defs_by_ghl_id:
            defn = defs_by_ghl_id[ghl_def_id]
        elif field_key and field_key in defs_by_field_key:
            defn = defs_by_field_key[field_key]

        if not defn:
            continue

        raw_value = _extract_custom_field_value(item)

        stmt = select(CustomFieldValue).where(
            CustomFieldValue.definition_id == defn.id,
            CustomFieldValue.entity_id == entity_id,
        )
        cfv = (await db.execute(stmt)).scalar_one_or_none()

        if not cfv:
            cfv = CustomFieldValue(
                definition_id=defn.id,
                entity_id=entity_id,
                entity_type=entity_type,
            )
            db.add(cfv)

        _apply_custom_field_value(cfv, data_type=defn.data_type, raw_value=raw_value)


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
        await upsert_raw_entity(
            db,
            location=location,
            entity_type="tag",
            ghl_id=ghl_id,
            payload=item,
        )

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
        await upsert_raw_entity(
            db,
            location=location,
            entity_type="custom_field_definition",
            ghl_id=ghl_id,
            payload=item,
        )

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
        await upsert_raw_entity(
            db,
            location=location,
            entity_type="custom_value",
            ghl_id=ghl_id,
            payload=item,
        )

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
        await upsert_raw_entity(
            db,
            location=location,
            entity_type="pipeline",
            ghl_id=ghl_id,
            payload=p_data,
        )

        pipeline = None
        if isinstance(ghl_id, str) and ghl_id:
            stmt = select(Pipeline).where(
                Pipeline.location_id == location.id, Pipeline.ghl_id == ghl_id
            )
            pipeline = (await db.execute(stmt)).scalar_one_or_none()

        if pipeline is None:
            stmt = select(Pipeline).where(
                Pipeline.location_id == location.id, Pipeline.name == name
            )
            pipeline = (await db.execute(stmt)).scalar_one_or_none()

        if pipeline:
            pipeline.name = name
            if (not pipeline.ghl_id) and isinstance(ghl_id, str) and ghl_id:
                pipeline.ghl_id = ghl_id
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
            await upsert_raw_entity(
                db,
                location=location,
                entity_type="pipeline_stage",
                ghl_id=s_ghl_id,
                payload=s_data,
            )

            stage = None
            if isinstance(s_ghl_id, str) and s_ghl_id:
                stmt = select(PipelineStage).where(
                    PipelineStage.pipeline_id == pipeline.id,
                    PipelineStage.ghl_id == s_ghl_id,
                )
                stage = (await db.execute(stmt)).scalar_one_or_none()

            if stage is None and isinstance(s_name, str) and s_name:
                stmt = select(PipelineStage).where(
                    PipelineStage.pipeline_id == pipeline.id,
                    PipelineStage.name == s_name,
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
            if (not stage.ghl_id) and isinstance(s_ghl_id, str) and s_ghl_id:
                stage.ghl_id = s_ghl_id

            if isinstance(s_ghl_id, str) and s_ghl_id:
                stage_map[s_ghl_id] = stage.id

    await db.commit()
    return result, stage_map


async def import_contacts(
    db: AsyncSession, location: Location, contacts_data: list[dict]
) -> tuple[SyncResult, dict[str, uuid.UUID]]:
    """Import contacts from GHL. Returns (result, contact_ghl_id_map)."""
    result = SyncResult()
    contact_map: dict[str, uuid.UUID] = {}

    defs_by_ghl_id, defs_by_field_key = await _load_custom_field_def_maps(
        db,
        location_id=location.id,
        entity_type="contact",
    )

    for c_data in contacts_data:
        ghl_id = c_data.get("id", c_data.get("_id", ""))
        await upsert_raw_entity(
            db,
            location=location,
            entity_type="contact",
            ghl_id=ghl_id,
            payload=c_data,
        )
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

        # Import contact custom field values
        await _upsert_custom_field_values(
            db,
            entity_id=contact.id,
            entity_type="contact",
            custom_fields_payload=c_data.get("customFields"),
            defs_by_ghl_id=defs_by_ghl_id,
            defs_by_field_key=defs_by_field_key,
        )

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

    defs_by_ghl_id, defs_by_field_key = await _load_custom_field_def_maps(
        db,
        location_id=location.id,
        entity_type="opportunity",
    )

    # Resolve pipeline
    stmt = select(Pipeline).where(
        Pipeline.location_id == location.id, Pipeline.ghl_id == pipeline_ghl_id
    )
    pipeline = (await db.execute(stmt)).scalar_one_or_none()
    if not pipeline:
        # Some accounts expose duplicate logical pipelines with different GHL IDs.
        # If direct pipeline ID lookup fails, infer the local pipeline via mapped
        # stage IDs present on the opportunities in this batch.
        for o_data in opps_data:
            ghl_stage_id = o_data.get("pipelineStageId", "")
            stage_local_id = stage_map.get(ghl_stage_id)
            if not stage_local_id:
                continue
            stage = await db.get(PipelineStage, stage_local_id)
            if not stage:
                continue
            pipeline = await db.get(Pipeline, stage.pipeline_id)
            if pipeline:
                break

    if not pipeline:
        result.errors.append(f"Pipeline {pipeline_ghl_id} not found locally")
        return result

    for o_data in opps_data:
        ghl_id = o_data.get("id", o_data.get("_id", ""))
        await upsert_raw_entity(
            db,
            location=location,
            entity_type="opportunity",
            ghl_id=ghl_id,
            payload=o_data,
        )
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
            await db.flush()
            result.created += 1

        # Import opportunity custom field values
        await _upsert_custom_field_values(
            db,
            entity_id=opp.id,
            entity_type="opportunity",
            custom_fields_payload=o_data.get("customFields"),
            defs_by_ghl_id=defs_by_ghl_id,
            defs_by_field_key=defs_by_field_key,
        )

    await db.commit()
    return result
