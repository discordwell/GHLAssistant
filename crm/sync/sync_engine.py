"""Sync orchestrator - coordinates import/export operations."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.location import Location
from ..schemas.sync import ImportPreview, SyncResult
from .importer import (
    import_tags,
    import_custom_fields,
    import_custom_values,
    import_pipelines,
    import_contacts,
    import_opportunities,
)
from .exporter import export_tags, export_contacts, export_opportunities
from .import_conversations import import_conversations
from .import_calendars import import_calendars
from .import_forms import import_forms
from .import_surveys import import_surveys
from .import_campaigns import import_campaigns
from .import_funnels import import_funnels
from .export_conversations import export_conversations
from .export_calendars import export_calendars


async def _get_ghl_client():
    """Get an authenticated GHL client."""
    from maxlevel.api import GHLClient
    return GHLClient.from_session()


async def preview_import(ghl_location_id: str) -> ImportPreview:
    """Preview what would be imported from GHL without making changes."""
    preview = ImportPreview()

    async with await _get_ghl_client() as ghl:
        # Snapshot config
        from maxlevel.blueprint.engine import snapshot_location
        snap = await snapshot_location(ghl, location_id=ghl_location_id)
        bp = snap.blueprint

        preview.tags = len(bp.tags)
        preview.custom_fields = len(bp.custom_fields)
        preview.custom_values = len(bp.custom_values)
        preview.pipelines = len(bp.pipelines)

        # Count contacts
        try:
            contacts_resp = await ghl.contacts.list(location_id=ghl_location_id, limit=1)
            preview.contacts = contacts_resp.get("meta", {}).get("total", 0)
        except Exception:
            preview.contacts = 0

        # Count opportunities per pipeline
        for p in bp.pipelines:
            pipeline_id = snap.id_map.get("pipelines", {}).get(p.name, "")
            if pipeline_id:
                try:
                    opps_resp = await ghl.opportunities.list(
                        pipeline_id=pipeline_id, location_id=ghl_location_id
                    )
                    preview.opportunities += len(opps_resp.get("opportunities", []))
                except Exception:
                    pass

        # Count conversations
        try:
            conv_resp = await ghl.conversations.list(location_id=ghl_location_id, limit=1)
            preview.conversations = conv_resp.get("total", len(conv_resp.get("conversations", [])))
        except Exception:
            pass

        # Count calendars
        try:
            cal_resp = await ghl.calendars.list(location_id=ghl_location_id)
            preview.calendars = len(cal_resp.get("calendars", []))
        except Exception:
            pass

        # Count forms
        try:
            forms_resp = await ghl.forms.list(location_id=ghl_location_id)
            preview.forms = len(forms_resp.get("forms", []))
        except Exception:
            pass

        # Count surveys
        try:
            surveys_resp = await ghl.surveys.list(location_id=ghl_location_id)
            preview.surveys = len(surveys_resp.get("surveys", []))
        except Exception:
            pass

        # Count campaigns
        try:
            camp_resp = await ghl.campaigns.list(location_id=ghl_location_id)
            preview.campaigns = len(camp_resp.get("campaigns", []))
        except Exception:
            pass

        # Count funnels
        try:
            funnel_resp = await ghl.funnels.list(location_id=ghl_location_id)
            preview.funnels = len(funnel_resp.get("funnels", []))
        except Exception:
            pass

    return preview


async def run_import(db: AsyncSession, location: Location) -> SyncResult:
    """Run full import from GHL to local CRM."""
    total = SyncResult()

    async with await _get_ghl_client() as ghl:
        lid = location.ghl_location_id

        # 1. Import config via snapshot
        from maxlevel.blueprint.engine import snapshot_location
        snap = await snapshot_location(ghl, location_id=lid)
        bp = snap.blueprint

        # 2. Tags
        tags_data = [{"id": snap.id_map.get("tags", {}).get(t.name, ""), "name": t.name}
                     for t in bp.tags]
        r = await import_tags(db, location, tags_data)
        total.created += r.created
        total.updated += r.updated

        # 3. Custom fields
        fields_data = [
            {
                "id": snap.id_map.get("custom_fields", {}).get(f.field_key, ""),
                "name": f.name,
                "fieldKey": f.field_key,
                "dataType": f.data_type,
            }
            for f in bp.custom_fields
        ]
        r = await import_custom_fields(db, location, fields_data)
        total.created += r.created
        total.updated += r.updated

        # 4. Custom values
        values_data = [
            {
                "id": snap.id_map.get("custom_values", {}).get(cv.name, ""),
                "name": cv.name,
                "value": cv.value,
            }
            for cv in bp.custom_values
        ]
        r = await import_custom_values(db, location, values_data)
        total.created += r.created
        total.updated += r.updated

        # 5. Pipelines
        pipelines_data = []
        for p in bp.pipelines:
            p_id = snap.id_map.get("pipelines", {}).get(p.name, "")
            pipelines_data.append({
                "id": p_id,
                "name": p.name,
                "stages": [
                    {
                        "id": snap.id_map.get("stages", {}).get(f"{p.name}:{s.name}", ""),
                        "name": s.name,
                    }
                    for s in p.stages
                ],
            })
        r, stage_map = await import_pipelines(db, location, pipelines_data)
        total.created += r.created
        total.updated += r.updated

        # 6. Contacts (paginated)
        all_contacts: list[dict] = []
        offset = 0
        while True:
            try:
                resp = await ghl.contacts.list(
                    location_id=lid, limit=100, offset=offset
                )
                batch = resp.get("contacts", [])
                if not batch:
                    break
                all_contacts.extend(batch)
                meta = resp.get("meta", {})
                if offset + len(batch) >= meta.get("total", 0):
                    break
                offset += len(batch)
            except Exception as e:
                total.errors.append(f"Contact pagination error: {e}")
                break

        r, contact_map = await import_contacts(db, location, all_contacts)
        total.created += r.created
        total.updated += r.updated

        # 7. Opportunities per pipeline
        for p_data in pipelines_data:
            p_id = p_data["id"]
            if not p_id:
                continue
            try:
                opps_resp = await ghl.opportunities.list(
                    pipeline_id=p_id, location_id=lid
                )
                opps_list = opps_resp.get("opportunities", [])
                r = await import_opportunities(
                    db, location, opps_list, stage_map, contact_map, p_id
                )
                total.created += r.created
                total.updated += r.updated
                total.errors.extend(r.errors)
            except Exception as e:
                total.errors.append(f"Opportunities import error: {e}")

        # 8. Conversations
        try:
            conv_resp = await ghl.conversations.list(location_id=lid, limit=100)
            conversations_data = conv_resp.get("conversations", [])
            messages_by_conv: dict[str, list[dict]] = {}
            for conv in conversations_data:
                conv_id = conv.get("id", conv.get("_id", ""))
                if conv_id:
                    try:
                        msg_resp = await ghl.conversations.messages(conv_id, limit=50)
                        raw = msg_resp.get("messages", [])
                        if isinstance(raw, dict):
                            messages_by_conv[conv_id] = raw.get("messages", [])
                        elif isinstance(raw, list):
                            messages_by_conv[conv_id] = raw
                    except Exception:
                        pass
            r = await import_conversations(db, location, conversations_data, messages_by_conv)
            total.created += r.created
            total.updated += r.updated
        except Exception as e:
            total.errors.append(f"Conversations import error: {e}")

        # 9. Calendars
        try:
            cal_resp = await ghl.calendars.list(location_id=lid)
            calendars_data = cal_resp.get("calendars", [])
            # Note: GHL calendar appointments endpoint may vary
            r = await import_calendars(db, location, calendars_data)
            total.created += r.created
            total.updated += r.updated
        except Exception as e:
            total.errors.append(f"Calendars import error: {e}")

        # 10. Forms
        try:
            forms_resp = await ghl.forms.list(location_id=lid)
            forms_data = forms_resp.get("forms", [])
            submissions_by_form: dict[str, list[dict]] = {}
            for form in forms_data:
                form_id = form.get("id", form.get("_id", ""))
                if form_id:
                    try:
                        sub_resp = await ghl.forms.submissions(
                            form_id, location_id=lid, limit=100
                        )
                        submissions_by_form[form_id] = sub_resp.get("submissions", [])
                    except Exception:
                        pass
            r = await import_forms(db, location, forms_data, submissions_by_form)
            total.created += r.created
            total.updated += r.updated
        except Exception as e:
            total.errors.append(f"Forms import error: {e}")

        # 11. Surveys
        try:
            surveys_resp = await ghl.surveys.list(location_id=lid)
            surveys_data = surveys_resp.get("surveys", [])
            submissions_by_survey: dict[str, list[dict]] = {}
            for survey in surveys_data:
                survey_id = survey.get("id", survey.get("_id", ""))
                if survey_id:
                    try:
                        sub_resp = await ghl.surveys.submissions(
                            survey_id, location_id=lid, limit=100
                        )
                        submissions_by_survey[survey_id] = sub_resp.get("submissions", [])
                    except Exception:
                        pass
            r = await import_surveys(db, location, surveys_data, submissions_by_survey)
            total.created += r.created
            total.updated += r.updated
        except Exception as e:
            total.errors.append(f"Surveys import error: {e}")

        # 12. Campaigns
        try:
            camp_resp = await ghl.campaigns.list(location_id=lid)
            campaigns_data = camp_resp.get("campaigns", [])
            r = await import_campaigns(db, location, campaigns_data)
            total.created += r.created
            total.updated += r.updated
        except Exception as e:
            total.errors.append(f"Campaigns import error: {e}")

        # 13. Funnels
        try:
            funnel_resp = await ghl.funnels.list(location_id=lid)
            funnels_data = funnel_resp.get("funnels", [])
            pages_by_funnel: dict[str, list[dict]] = {}
            for funnel in funnels_data:
                funnel_id = funnel.get("id", funnel.get("_id", ""))
                if funnel_id:
                    try:
                        pages_resp = await ghl.funnels.pages(funnel_id, location_id=lid)
                        pages_by_funnel[funnel_id] = pages_resp.get("pages", [])
                    except Exception:
                        pass
            r = await import_funnels(db, location, funnels_data, pages_by_funnel)
            total.created += r.created
            total.updated += r.updated
        except Exception as e:
            total.errors.append(f"Funnels import error: {e}")

    return total


async def run_export(db: AsyncSession, location: Location) -> SyncResult:
    """Run full export from local CRM to GHL."""
    total = SyncResult()

    async with await _get_ghl_client() as ghl:
        # 1. Tags
        r = await export_tags(db, location, ghl)
        total.created += r.created
        total.updated += r.updated
        total.errors.extend(r.errors)

        # 2. Contacts
        r = await export_contacts(db, location, ghl)
        total.created += r.created
        total.updated += r.updated
        total.errors.extend(r.errors)

        # 3. Opportunities
        r = await export_opportunities(db, location, ghl)
        total.created += r.created
        total.updated += r.updated
        total.errors.extend(r.errors)

        # 4. Conversations (outbound messages)
        r = await export_conversations(db, location, ghl)
        total.created += r.created
        total.skipped += r.skipped
        total.errors.extend(r.errors)

        # 5. Calendar appointments
        r = await export_calendars(db, location, ghl)
        total.created += r.created
        total.skipped += r.skipped
        total.errors.extend(r.errors)

    return total
