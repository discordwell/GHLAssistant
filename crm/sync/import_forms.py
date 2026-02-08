"""Import forms and submissions from GHL."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.form import Form, FormField, FormSubmission
from ..models.contact import Contact
from ..models.location import Location
from ..schemas.sync import SyncResult


def _to_dict(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    return {}


def _extract_form_payload(detail: dict) -> dict:
    if not detail:
        return {}
    if isinstance(detail.get("form"), dict):
        return detail["form"]
    return detail


def _extract_fields(form_payload: dict, list_payload: dict) -> list[dict]:
    for source in (form_payload, list_payload):
        src = _to_dict(source)
        for key in ("fields", "formFields", "elements"):
            value = src.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _build_options_json(field_data: dict) -> dict | None:
    options: dict = {}

    raw_options = field_data.get("options", field_data.get("choices"))
    if isinstance(raw_options, dict):
        options.update(raw_options)
    elif isinstance(raw_options, list):
        options["options"] = raw_options

    ghl_field_id = field_data.get("id", field_data.get("_id"))
    if isinstance(ghl_field_id, str) and ghl_field_id:
        options["_ghl_field_id"] = ghl_field_id

    options["_ghl_raw"] = field_data
    return options if options else None


async def import_forms(
    db: AsyncSession, location: Location, forms_data: list[dict],
    submissions_by_form: dict[str, list[dict]] | None = None,
    details_by_form: dict[str, dict] | None = None,
) -> SyncResult:
    """Import forms, fields, and submissions from GHL."""
    result = SyncResult()
    submissions_by_form = submissions_by_form or {}
    details_by_form = details_by_form or {}

    for f_data in forms_data:
        ghl_id = f_data.get("id", f_data.get("_id", ""))
        name = f_data.get("name", "")
        if not name:
            continue

        detail_payload = _extract_form_payload(_to_dict(details_by_form.get(ghl_id)))
        description = detail_payload.get("description", f_data.get("description"))
        is_active = detail_payload.get("isActive", detail_payload.get("active", True))
        if not isinstance(is_active, bool):
            is_active = bool(is_active)

        stmt = select(Form).where(
            Form.location_id == location.id, Form.ghl_id == ghl_id
        )
        form = (await db.execute(stmt)).scalar_one_or_none()

        if form:
            form.name = name
            form.description = description
            form.is_active = is_active
            form.last_synced_at = datetime.now(timezone.utc)
            result.updated += 1
        else:
            form = Form(
                location_id=location.id, name=name,
                description=description, is_active=is_active,
                ghl_id=ghl_id, ghl_location_id=location.ghl_location_id,
                last_synced_at=datetime.now(timezone.utc),
            )
            db.add(form)
            await db.flush()
            result.created += 1

        # Import/update fields
        fields_data = _extract_fields(detail_payload, _to_dict(f_data))
        for i, field_data in enumerate(fields_data):
            label = (
                field_data.get("label")
                or field_data.get("name")
                or field_data.get("placeholder")
                or f"Field {i + 1}"
            )
            field_type = str(
                field_data.get("fieldType", field_data.get("type", "text"))
            ).lower()
            is_required = bool(field_data.get("isRequired", field_data.get("required", False)))
            placeholder = field_data.get("placeholder")
            options_json = _build_options_json(field_data)

            stmt = select(FormField).where(
                FormField.form_id == form.id, FormField.position == i
            )
            field = (await db.execute(stmt)).scalar_one_or_none()

            if field:
                field.label = label
                field.field_type = field_type
                field.is_required = is_required
                field.placeholder = placeholder
                field.options_json = options_json
            else:
                field = FormField(
                    form_id=form.id,
                    label=label,
                    field_type=field_type,
                    is_required=is_required,
                    options_json=options_json,
                    position=i,
                    placeholder=placeholder,
                )
                db.add(field)

        # Import submissions (dedup by submitted_at + form_id)
        existing_stmt = select(FormSubmission).where(FormSubmission.form_id == form.id)
        existing_submissions = list((await db.execute(existing_stmt)).scalars().all())
        existing_ghl_submission_ids = {
            sub.data_json.get("_ghl_submission_id")
            for sub in existing_submissions
            if isinstance(sub.data_json, dict) and sub.data_json.get("_ghl_submission_id")
        }

        for sub_data in submissions_by_form.get(ghl_id, []):
            sub_ghl_id = sub_data.get("id", sub_data.get("_id"))
            if isinstance(sub_ghl_id, str) and sub_ghl_id in existing_ghl_submission_ids:
                continue

            submitted_at_raw = sub_data.get("createdAt", sub_data.get("submittedAt"))
            if submitted_at_raw:
                try:
                    parsed_ts = datetime.fromisoformat(submitted_at_raw.replace("Z", "+00:00"))
                    dup_stmt = select(FormSubmission).where(
                        FormSubmission.form_id == form.id,
                        FormSubmission.submitted_at == parsed_ts,
                    )
                    if (await db.execute(dup_stmt)).scalar_one_or_none():
                        continue
                except (ValueError, AttributeError):
                    pass

            payload_data = sub_data.get("data", sub_data.get("others", {}))
            if not isinstance(payload_data, dict):
                payload_data = {"value": payload_data}
            else:
                payload_data = dict(payload_data)

            raw_submission = copy.deepcopy(sub_data)

            if isinstance(sub_ghl_id, str) and sub_ghl_id:
                payload_data["_ghl_submission_id"] = sub_ghl_id
            payload_data["_ghl_raw"] = raw_submission

            contact_id = None
            ghl_contact_id = sub_data.get("contactId")
            if isinstance(ghl_contact_id, str) and ghl_contact_id:
                contact_stmt = select(Contact).where(
                    Contact.location_id == location.id,
                    Contact.ghl_id == ghl_contact_id,
                )
                contact = (await db.execute(contact_stmt)).scalar_one_or_none()
                if contact:
                    contact_id = contact.id

            sub = FormSubmission(
                location_id=location.id,
                form_id=form.id,
                contact_id=contact_id,
                data_json=payload_data,
                source_ip=sub_data.get("ip"),
            )
            submitted_at = sub_data.get("createdAt", sub_data.get("submittedAt"))
            if submitted_at:
                try:
                    sub.submitted_at = datetime.fromisoformat(
                        submitted_at.replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    pass
            db.add(sub)
            if isinstance(sub_ghl_id, str) and sub_ghl_id:
                existing_ghl_submission_ids.add(sub_ghl_id)

    await db.commit()
    return result
