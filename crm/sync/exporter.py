"""Local CRM -> GHL exporter."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.contact import Contact
from ..models.custom_field import CustomFieldDefinition, CustomFieldValue
from ..models.tag import Tag
from ..models.pipeline import Pipeline, PipelineStage
from ..models.opportunity import Opportunity
from ..models.note import Note
from ..models.task import Task
from ..models.location import Location
from ..schemas.sync import SyncResult
from .field_mapper import local_contact_to_ghl, local_opportunity_to_ghl


def _cfv_value(cfv: CustomFieldValue) -> Any:
    """Return the best-effort value payload for a custom field value row."""
    if cfv.value_bool is not None:
        return cfv.value_bool
    if cfv.value_number is not None:
        return cfv.value_number
    if cfv.value_date is not None:
        return cfv.value_date
    return cfv.value_text


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
    stmt = (
        select(Contact)
        .where(Contact.location_id == location.id)
        .options(selectinload(Contact.tags))
    )
    contacts = list((await db.execute(stmt)).scalars().all())

    # Preload contact custom field values and group them by local contact UUID.
    custom_fields_by_entity: dict = {}
    cf_stmt = (
        select(CustomFieldValue, CustomFieldDefinition)
        .join(CustomFieldDefinition, CustomFieldValue.definition_id == CustomFieldDefinition.id)
        .where(
            CustomFieldDefinition.location_id == location.id,
            CustomFieldValue.entity_type == "contact",
        )
    )
    rows = (await db.execute(cf_stmt)).all()
    for cfv, defn in rows:
        custom_fields_by_entity.setdefault(cfv.entity_id, []).append((defn, cfv))

    for contact in contacts:
        ghl_data = local_contact_to_ghl(contact)
        ghl_data["locationId"] = location.ghl_location_id

        # Include tags by name.
        if getattr(contact, "tags", None):
            ghl_data["tags"] = [t.name for t in contact.tags if getattr(t, "name", None)]

        # Include custom field values as a list of {id/fieldKey, value} items.
        cf_items: list[dict[str, Any]] = []
        for defn, cfv in custom_fields_by_entity.get(contact.id, []):
            value = _cfv_value(cfv)
            if value is None:
                continue
            item: dict[str, Any] = {"value": value}
            if isinstance(defn.ghl_id, str) and defn.ghl_id:
                item["id"] = defn.ghl_id
            if isinstance(defn.field_key, str) and defn.field_key:
                item["fieldKey"] = defn.field_key
            cf_items.append(item)

        if cf_items:
            ghl_data["customFields"] = cf_items

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


async def export_notes(db: AsyncSession, location: Location, ghl) -> SyncResult:
    """Export local notes to GHL (best-effort, create-only)."""
    result = SyncResult()

    stmt = (
        select(Note)
        .where(Note.location_id == location.id, Note.ghl_id == None)  # noqa: E711
        .options(selectinload(Note.contact))
        .order_by(Note.created_at.asc())
    )
    notes = list((await db.execute(stmt)).scalars().all())

    for note in notes:
        if not getattr(note, "contact", None) or not getattr(note.contact, "ghl_id", None):
            result.errors.append(f"Note {note.id}: missing contact GHL id")
            continue
        try:
            resp = await ghl.contacts.add_note(
                note.contact.ghl_id,
                note.body,
                location_id=location.ghl_location_id,
            )
            payload = resp.get("note", resp) if isinstance(resp, dict) else {}
            ghl_id = payload.get("id", payload.get("_id", "")) if isinstance(payload, dict) else ""
            if isinstance(ghl_id, str) and ghl_id:
                note.ghl_id = ghl_id
                note.ghl_location_id = location.ghl_location_id
                note.last_synced_at = datetime.now(timezone.utc)
                result.created += 1
            else:
                result.errors.append(f"Note {note.id}: export succeeded but no id returned")
        except Exception as e:
            result.errors.append(f"Note {note.id}: {e}")

    await db.commit()
    return result


async def export_tasks(db: AsyncSession, location: Location, ghl) -> SyncResult:
    """Export local tasks to GHL (best-effort, create-only)."""
    result = SyncResult()

    stmt = (
        select(Task)
        .where(Task.location_id == location.id, Task.ghl_id == None)  # noqa: E711
        .options(selectinload(Task.contact))
        .order_by(Task.created_at.asc())
    )
    tasks = list((await db.execute(stmt)).scalars().all())

    for task in tasks:
        if not getattr(task, "contact", None) or not getattr(task.contact, "ghl_id", None):
            result.errors.append(f"Task {task.id}: missing contact GHL id")
            continue

        due_iso = task.due_date.isoformat() if getattr(task, "due_date", None) else None
        try:
            resp = await ghl.contacts.add_task(
                task.contact.ghl_id,
                task.title,
                due_date=due_iso,
                description=task.description,
                location_id=location.ghl_location_id,
            )
            payload = resp.get("task", resp) if isinstance(resp, dict) else {}
            ghl_id = payload.get("id", payload.get("_id", "")) if isinstance(payload, dict) else ""
            if isinstance(ghl_id, str) and ghl_id:
                task.ghl_id = ghl_id
                task.ghl_location_id = location.ghl_location_id
                task.last_synced_at = datetime.now(timezone.utc)
                result.created += 1
            else:
                result.errors.append(f"Task {task.id}: export succeeded but no id returned")
        except Exception as e:
            result.errors.append(f"Task {task.id}: {e}")

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

    # Preload opportunity custom field values and group by local opportunity UUID.
    custom_fields_by_entity: dict = {}
    cf_stmt = (
        select(CustomFieldValue, CustomFieldDefinition)
        .join(CustomFieldDefinition, CustomFieldValue.definition_id == CustomFieldDefinition.id)
        .where(
            CustomFieldDefinition.location_id == location.id,
            CustomFieldValue.entity_type == "opportunity",
        )
    )
    rows = (await db.execute(cf_stmt)).all()
    for cfv, defn in rows:
        custom_fields_by_entity.setdefault(cfv.entity_id, []).append((defn, cfv))

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

        # Include custom field values if any exist locally.
        cf_items: list[dict[str, Any]] = []
        for defn, cfv in custom_fields_by_entity.get(opp.id, []):
            value = _cfv_value(cfv)
            if value is None:
                continue
            item: dict[str, Any] = {"value": value}
            if isinstance(defn.ghl_id, str) and defn.ghl_id:
                item["id"] = defn.ghl_id
            if isinstance(defn.field_key, str) and defn.field_key:
                item["fieldKey"] = defn.field_key
            cf_items.append(item)
        if cf_items:
            ghl_data["customFields"] = cf_items

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
