"""Local CRM -> GHL exporter."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.contact import Contact
from ..models.custom_field import CustomFieldDefinition, CustomFieldValue
from ..models.custom_value import CustomValue
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


def _normalize_name(value: str | None) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().lower().split())


def _extract_ghl_id(payload: dict[str, Any] | None) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("id", "_id"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _as_utc(dt: datetime) -> datetime:
    """Normalize naive/aware datetimes into UTC-aware datetimes for comparisons."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _needs_update(updated_at: datetime | None, last_synced_at: datetime | None) -> bool:
    """Return True if local row should be exported as an update."""
    if last_synced_at is None:
        # Unknown sync state: safest is to push an update.
        return True
    if updated_at is None:
        # If we can't tell, treat as changed.
        return True
    return _as_utc(updated_at) > _as_utc(last_synced_at)


def _date_to_ghl_due_date(value: date) -> str:
    # Common services-domain payload shape uses an ISO datetime string.
    return f"{value.isoformat()}T00:00:00.000Z"


def _map_custom_field_data_type(local_data_type: str | None) -> str:
    """Map local data_type (lowercase) to GHL expected dataType."""
    dt = (local_data_type or "").strip().lower()
    if dt in {"text", "string"}:
        return "TEXT"
    if dt in {"textarea", "longtext"}:
        return "TEXTAREA"
    if dt in {"number", "numeric", "float", "int"}:
        return "NUMBER"
    if dt in {"date", "datetime"}:
        return "DATE"
    if dt in {"boolean", "bool", "checkbox"}:
        return "CHECKBOX"
    if dt in {"select", "dropdown", "picklist"}:
        return "DROPDOWN"
    return (local_data_type or "TEXT").upper()


async def export_custom_fields(db: AsyncSession, location: Location, ghl) -> SyncResult:
    """Export local custom field definitions to GHL (API-backed)."""
    result = SyncResult()
    now = datetime.now(timezone.utc)

    stmt = (
        select(CustomFieldDefinition)
        .where(CustomFieldDefinition.location_id == location.id)
        .order_by(CustomFieldDefinition.position.asc(), CustomFieldDefinition.created_at.asc())
    )
    defs = list((await db.execute(stmt)).scalars().all())
    if not defs:
        return result

    remote_fields: list[dict[str, Any]] = []
    if getattr(location, "ghl_location_id", None):
        try:
            resp = await ghl.custom_fields.list(location_id=location.ghl_location_id)
            raw = resp.get("customFields", [])
            if isinstance(raw, list):
                remote_fields = [item for item in raw if isinstance(item, dict)]
        except Exception as exc:
            result.errors.append(f"Custom fields list failed: {exc}")

    remote_by_field_key: dict[str, dict[str, Any]] = {}
    remote_by_name: dict[str, dict[str, Any]] = {}
    for remote in remote_fields:
        field_key = remote.get("fieldKey")
        if isinstance(field_key, str) and field_key and field_key not in remote_by_field_key:
            remote_by_field_key[field_key] = remote
        name_key = _normalize_name(str(remote.get("name", "")))
        if name_key and name_key not in remote_by_name:
            remote_by_name[name_key] = remote

    for defn in defs:
        try:
            # Best-effort reconcile missing IDs by fieldKey, then by name.
            if not defn.ghl_id:
                remote = None
                if isinstance(defn.field_key, str) and defn.field_key:
                    remote = remote_by_field_key.get(defn.field_key)
                if remote is None:
                    remote = remote_by_name.get(_normalize_name(defn.name))
                remote_id = _extract_ghl_id(remote)
                if remote_id:
                    defn.ghl_id = remote_id
                    defn.ghl_location_id = location.ghl_location_id
                    defn.last_synced_at = now
                    result.updated += 1
                    continue

            data_type = _map_custom_field_data_type(defn.data_type)
            placeholder = None
            if isinstance(defn.options_json, dict):
                placeholder = defn.options_json.get("placeholder")
                if not isinstance(placeholder, str):
                    placeholder = None

            if defn.ghl_id:
                await ghl.custom_fields.update(
                    defn.ghl_id,
                    name=defn.name,
                    placeholder=placeholder,
                    position=defn.position,
                    location_id=location.ghl_location_id,
                )
                defn.last_synced_at = now
                result.updated += 1
            else:
                resp = await ghl.custom_fields.create(
                    name=defn.name,
                    field_key=defn.field_key,
                    data_type=data_type,
                    placeholder=placeholder,
                    position=defn.position,
                    location_id=location.ghl_location_id,
                )
                payload = resp.get("customField", resp) if isinstance(resp, dict) else {}
                remote_id = _extract_ghl_id(payload)
                if not remote_id:
                    result.errors.append(f"Custom field '{defn.field_key}': created but no id returned")
                    continue
                defn.ghl_id = remote_id
                defn.ghl_location_id = location.ghl_location_id
                defn.last_synced_at = now
                result.created += 1
        except Exception as exc:
            result.errors.append(f"Custom field '{getattr(defn, 'field_key', defn.id)}': {exc}")

    await db.commit()
    return result


async def export_custom_values(db: AsyncSession, location: Location, ghl) -> SyncResult:
    """Export local custom values to GHL (API-backed)."""
    result = SyncResult()
    now = datetime.now(timezone.utc)

    stmt = (
        select(CustomValue)
        .where(CustomValue.location_id == location.id)
        .order_by(CustomValue.created_at.asc())
    )
    values = list((await db.execute(stmt)).scalars().all())
    if not values:
        return result

    remote_values: list[dict[str, Any]] = []
    if getattr(location, "ghl_location_id", None):
        try:
            resp = await ghl.custom_values.list(location_id=location.ghl_location_id)
            raw = resp.get("customValues", [])
            if isinstance(raw, list):
                remote_values = [item for item in raw if isinstance(item, dict)]
        except Exception as exc:
            result.errors.append(f"Custom values list failed: {exc}")

    remote_by_name: dict[str, dict[str, Any]] = {}
    for remote in remote_values:
        name_key = _normalize_name(str(remote.get("name", "")))
        if name_key and name_key not in remote_by_name:
            remote_by_name[name_key] = remote

    for cv in values:
        try:
            if not cv.ghl_id:
                remote = remote_by_name.get(_normalize_name(cv.name))
                remote_id = _extract_ghl_id(remote)
                if remote_id:
                    cv.ghl_id = remote_id
                    cv.ghl_location_id = location.ghl_location_id
                    cv.last_synced_at = now
                    result.updated += 1
                    continue

            if cv.ghl_id:
                await ghl.custom_values.update(
                    cv.ghl_id,
                    name=cv.name,
                    value=cv.value or "",
                    location_id=location.ghl_location_id,
                )
                cv.last_synced_at = now
                result.updated += 1
            else:
                resp = await ghl.custom_values.create(
                    name=cv.name,
                    value=cv.value or "",
                    location_id=location.ghl_location_id,
                )
                payload = resp.get("customValue", resp) if isinstance(resp, dict) else {}
                remote_id = _extract_ghl_id(payload)
                if not remote_id:
                    result.errors.append(f"Custom value '{cv.name}': created but no id returned")
                    continue
                cv.ghl_id = remote_id
                cv.ghl_location_id = location.ghl_location_id
                cv.last_synced_at = now
                result.created += 1
        except Exception as exc:
            result.errors.append(f"Custom value '{getattr(cv, 'name', cv.id)}': {exc}")

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
    """Export local notes to GHL (best-effort)."""
    result = SyncResult()

    stmt = (
        select(Note)
        .where(Note.location_id == location.id)
        .options(selectinload(Note.contact))
        .order_by(Note.created_at.asc())
    )
    notes = list((await db.execute(stmt)).scalars().all())

    token_id = getattr(getattr(ghl, "config", None), "token_id", None)
    use_services = isinstance(token_id, str) and bool(token_id.strip())

    for note in notes:
        contact_ghl_id = getattr(getattr(note, "contact", None), "ghl_id", None)
        now = datetime.now(timezone.utc)

        # Update existing note in GHL when the local row changed after last sync.
        if getattr(note, "ghl_id", None):
            if not _needs_update(getattr(note, "updated_at", None), getattr(note, "last_synced_at", None)):
                result.skipped += 1
                continue
            if not use_services:
                result.errors.append(
                    f"Note {note.id}: cannot update without services token-id (run capture/auth quick)"
                )
                continue
            try:
                await ghl.notes_service.update(  # type: ignore[attr-defined]
                    note.ghl_id,
                    location_id=location.ghl_location_id,
                    body=note.body,
                )
                note.ghl_location_id = location.ghl_location_id
                note.last_synced_at = now
                result.updated += 1
            except Exception as e:
                result.errors.append(f"Note {note.id}: {e}")
            continue

        # Create missing note in GHL.
        if not isinstance(contact_ghl_id, str) or not contact_ghl_id:
            result.errors.append(f"Note {note.id}: missing contact GHL id")
            continue
        try:
            if use_services:
                resp = await ghl.notes_service.create(  # type: ignore[attr-defined]
                    location_id=location.ghl_location_id,
                    body=note.body,
                    contact_id=contact_ghl_id,
                )
                payload = resp.get("note", resp) if isinstance(resp, dict) else {}
            else:
                # Fallback: backend contact endpoint (create-only).
                resp = await ghl.contacts.add_note(  # type: ignore[attr-defined]
                    contact_ghl_id,
                    note.body,
                    location_id=location.ghl_location_id,
                )
                payload = resp.get("note", resp) if isinstance(resp, dict) else {}

            ghl_id = _extract_ghl_id(payload)
            if isinstance(ghl_id, str) and ghl_id:
                note.ghl_id = ghl_id
                note.ghl_location_id = location.ghl_location_id
                note.last_synced_at = now
                result.created += 1
            else:
                result.errors.append(f"Note {note.id}: export succeeded but no id returned")
        except Exception as e:
            result.errors.append(f"Note {note.id}: {e}")

    await db.commit()
    return result


async def export_tasks(db: AsyncSession, location: Location, ghl) -> SyncResult:
    """Export local tasks to GHL (best-effort)."""
    result = SyncResult()

    stmt = (
        select(Task)
        .where(Task.location_id == location.id)
        .options(selectinload(Task.contact))
        .order_by(Task.created_at.asc())
    )
    tasks = list((await db.execute(stmt)).scalars().all())

    token_id = getattr(getattr(ghl, "config", None), "token_id", None)
    use_services = isinstance(token_id, str) and bool(token_id.strip())

    for task in tasks:
        now = datetime.now(timezone.utc)
        due_date_val = getattr(task, "due_date", None)
        due_iso = _date_to_ghl_due_date(due_date_val) if isinstance(due_date_val, date) else None

        status_l = str(getattr(task, "status", "") or "").strip().lower()
        remote_status = "completed" if status_l == "done" else "incomplete"

        # Update existing task in GHL when local row changed after last sync.
        if getattr(task, "ghl_id", None):
            if not _needs_update(getattr(task, "updated_at", None), getattr(task, "last_synced_at", None)):
                result.skipped += 1
                continue
            if not use_services:
                result.errors.append(
                    f"Task {task.id}: cannot update without services token-id (run capture/auth quick)"
                )
                continue
            try:
                await ghl.tasks_service.update(  # type: ignore[attr-defined]
                    task.ghl_id,
                    location_id=location.ghl_location_id,
                    title=task.title,
                    due_date=due_iso,
                    description=task.description,
                    status=remote_status,
                    assigned_to=task.assigned_to,
                )
                task.ghl_location_id = location.ghl_location_id
                task.last_synced_at = now
                result.updated += 1
            except Exception as e:
                result.errors.append(f"Task {task.id}: {e}")
            continue

        # Create missing task in GHL.
        contact_ghl_id = getattr(getattr(task, "contact", None), "ghl_id", None)
        try:
            if use_services:
                resp = await ghl.tasks_service.create(  # type: ignore[attr-defined]
                    location_id=location.ghl_location_id,
                    title=task.title,
                    contact_id=contact_ghl_id if isinstance(contact_ghl_id, str) and contact_ghl_id else None,
                    due_date=due_iso,
                    description=task.description,
                    status=remote_status,
                    assigned_to=task.assigned_to,
                )
                payload = resp.get("record", resp) if isinstance(resp, dict) else {}
            else:
                # Fallback: backend contact endpoint (create-only, requires contact + due date).
                if not isinstance(contact_ghl_id, str) or not contact_ghl_id:
                    result.errors.append(f"Task {task.id}: missing contact GHL id")
                    continue
                resp = await ghl.contacts.add_task(  # type: ignore[attr-defined]
                    contact_ghl_id,
                    task.title,
                    due_date=due_date_val.isoformat() if isinstance(due_date_val, date) else None,
                    description=task.description,
                    location_id=location.ghl_location_id,
                )
                payload = resp.get("task", resp) if isinstance(resp, dict) else {}

            ghl_id = _extract_ghl_id(payload)
            if isinstance(ghl_id, str) and ghl_id:
                task.ghl_id = ghl_id
                task.ghl_location_id = location.ghl_location_id
                task.last_synced_at = now
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

    def _norm(value: str | None) -> str:
        if not isinstance(value, str):
            return ""
        return " ".join(value.strip().lower().split())

    def _extract_id(payload: dict[str, Any] | None) -> str:
        if not isinstance(payload, dict):
            return ""
        for key in ("id", "_id"):
            val = payload.get(key)
            if isinstance(val, str) and val:
                return val
        return ""

    # If any local pipeline/stage rows are missing GHL IDs, attempt best-effort
    # mapping to existing remote pipelines by name before exporting.
    pipelines_by_name: dict[str, dict[str, Any]] = {}
    pipelines_by_id: dict[str, dict[str, Any]] = {}
    needs_pipeline_mapping = any(
        (getattr(opp, "pipeline", None) and not getattr(opp.pipeline, "ghl_id", None))
        or (getattr(opp, "stage", None) and not getattr(opp.stage, "ghl_id", None))
        for opp in opps
    )
    if needs_pipeline_mapping and getattr(location, "ghl_location_id", None):
        try:
            resp = await ghl.opportunities.pipelines(location_id=location.ghl_location_id)
            remote = resp.get("pipelines", resp)
            remote_pipelines = remote if isinstance(remote, list) else resp.get("pipelines", [])
            if not isinstance(remote_pipelines, list):
                remote_pipelines = []
        except Exception as exc:
            remote_pipelines = []
            result.errors.append(f"Opportunity export: pipeline list failed: {exc}")

        for p in remote_pipelines:
            if not isinstance(p, dict):
                continue
            pid = _extract_id(p)
            if pid and pid not in pipelines_by_id:
                pipelines_by_id[pid] = p
            name_key = _norm(str(p.get("name", "")))
            if name_key and name_key not in pipelines_by_name:
                pipelines_by_name[name_key] = p

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

        # Best-effort: fill in missing pipeline/stage GHL IDs by name matching.
        remote_pipeline: dict[str, Any] | None = None
        if getattr(opp, "pipeline", None) is not None and not getattr(opp.pipeline, "ghl_id", None):
            remote_pipeline = pipelines_by_name.get(_norm(getattr(opp.pipeline, "name", "")))
            remote_id = _extract_id(remote_pipeline)
            if remote_id:
                opp.pipeline.ghl_id = remote_id
                opp.pipeline.ghl_location_id = location.ghl_location_id
                opp.pipeline.last_synced_at = datetime.now(timezone.utc)

        if getattr(opp, "pipeline", None) is not None and getattr(opp.pipeline, "ghl_id", None):
            remote_pipeline = pipelines_by_id.get(str(opp.pipeline.ghl_id)) or remote_pipeline

        if getattr(opp, "stage", None) is not None and not getattr(opp.stage, "ghl_id", None) and remote_pipeline:
            remote_stages_raw = remote_pipeline.get("stages", [])
            remote_stages: list[dict[str, Any]] = (
                [s for s in remote_stages_raw if isinstance(s, dict)]
                if isinstance(remote_stages_raw, list)
                else []
            )
            stage_by_name: dict[str, dict[str, Any]] = {}
            for s in remote_stages:
                key = _norm(str(s.get("name", "")))
                if key and key not in stage_by_name:
                    stage_by_name[key] = s

            remote_stage = stage_by_name.get(_norm(getattr(opp.stage, "name", "")))
            if remote_stage is None:
                try:
                    remote_stage = remote_stages[int(getattr(opp.stage, "position", 0))]
                except Exception:
                    remote_stage = None
            remote_stage_id = _extract_id(remote_stage)
            if remote_stage_id:
                opp.stage.ghl_id = remote_stage_id
                opp.stage.ghl_location_id = location.ghl_location_id
                opp.stage.last_synced_at = datetime.now(timezone.utc)

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
