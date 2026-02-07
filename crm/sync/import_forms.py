"""Import forms and submissions from GHL."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.form import Form, FormField, FormSubmission
from ..models.location import Location
from ..schemas.sync import SyncResult


async def import_forms(
    db: AsyncSession, location: Location, forms_data: list[dict],
    submissions_by_form: dict[str, list[dict]] | None = None,
) -> SyncResult:
    """Import forms, fields, and submissions from GHL."""
    result = SyncResult()
    submissions_by_form = submissions_by_form or {}

    for f_data in forms_data:
        ghl_id = f_data.get("id", f_data.get("_id", ""))
        name = f_data.get("name", "")
        if not name:
            continue

        stmt = select(Form).where(
            Form.location_id == location.id, Form.ghl_id == ghl_id
        )
        form = (await db.execute(stmt)).scalar_one_or_none()

        if form:
            form.name = name
            form.last_synced_at = datetime.now(timezone.utc)
            result.updated += 1
        else:
            form = Form(
                location_id=location.id, name=name,
                ghl_id=ghl_id, ghl_location_id=location.ghl_location_id,
                last_synced_at=datetime.now(timezone.utc),
            )
            db.add(form)
            await db.flush()
            result.created += 1

        # Import submissions (dedup by submitted_at + form_id)
        for sub_data in submissions_by_form.get(ghl_id, []):
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
            sub = FormSubmission(
                location_id=location.id,
                form_id=form.id,
                data_json=sub_data.get("data", sub_data.get("others", {})),
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

    await db.commit()
    return result
