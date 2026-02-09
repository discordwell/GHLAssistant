"""Sync orchestrator - coordinates import/export operations."""

from __future__ import annotations

import asyncio

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
from .exporter import (
    export_tags,
    export_custom_fields,
    export_custom_values,
    export_contacts,
    export_notes,
    export_tasks,
    export_opportunities,
)
from .import_conversations import import_conversations
from .import_calendars import import_calendars
from .import_forms import import_forms
from .import_surveys import import_surveys
from .import_campaigns import import_campaigns
from .import_funnels import import_funnels
from .import_notes import import_notes
from .import_tasks import import_tasks
from .import_workflows import import_workflows
from .export_conversations import export_conversations
from .export_calendars import export_calendars
from .export_workflows import export_workflows_via_browser
from .archive import write_sync_archive
from .browser_fallback import export_browser_backed_resources
from ..config import settings


async def _get_ghl_client():
    """Get an authenticated GHL client."""
    from maxlevel.api import GHLClient
    return GHLClient.from_session()


def _extract_items(resp: dict, key: str) -> list[dict]:
    """Extract list items from a response key, handling wrapped payloads."""
    raw = resp.get(key, [])
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        nested = raw.get(key)
        if isinstance(nested, list):
            return nested
    return []


def _extract_total(resp: dict, fallback: int) -> int:
    """Extract total count from common response metadata shapes."""
    meta = resp.get("meta", {})
    if isinstance(meta, dict):
        total = meta.get("total")
        if isinstance(total, int):
            return total

    total = resp.get("total")
    if isinstance(total, int):
        return total

    return fallback


async def _paginate_offset(
    fetch_page,
    key: str,
    page_size: int = 100,
    max_pages: int = 100,
) -> list[dict]:
    """Paginate endpoints that support limit/offset."""
    all_items: list[dict] = []
    seen_ids: set[str] = set()
    offset = 0

    for _ in range(max_pages):
        resp = await fetch_page(page_size, offset)
        batch = _extract_items(resp, key)
        if not batch:
            break

        new_count = 0
        for item in batch:
            item_id = item.get("id", item.get("_id", ""))
            if item_id:
                if item_id in seen_ids:
                    continue
                seen_ids.add(item_id)
            all_items.append(item)
            new_count += 1

        # Defensive guard when the API ignores offsets and returns the same page.
        if new_count == 0:
            break

        total = _extract_total(resp, len(all_items))
        if len(all_items) >= total:
            break

        offset += len(batch)

    return all_items


async def _paginate_start_after(
    fetch_page,
    key: str,
    page_size: int = 100,
    max_pages: int = 2000,
) -> list[dict]:
    """Paginate endpoints that use startAfter/startAfterId cursors (e.g. contacts)."""
    all_items: list[dict] = []
    seen_ids: set[str] = set()

    start_after_id: str | None = None
    start_after: int | None = None

    for _ in range(max_pages):
        resp = await fetch_page(page_size, start_after_id, start_after)
        batch = _extract_items(resp, key)
        if not batch:
            break

        new_count = 0
        for item in batch:
            item_id = item.get("id", item.get("_id", ""))
            if item_id:
                if item_id in seen_ids:
                    continue
                seen_ids.add(item_id)
            all_items.append(item)
            new_count += 1

        # Defensive guard when the API returns the same cursor page repeatedly.
        if new_count == 0:
            break

        meta = resp.get("meta", {})
        if not isinstance(meta, dict):
            break

        next_start_after_id = meta.get("startAfterId")
        next_start_after = meta.get("startAfter")

        if not isinstance(next_start_after_id, str) or not next_start_after_id:
            break
        if not isinstance(next_start_after, int):
            break

        if next_start_after_id == start_after_id and next_start_after == start_after:
            break

        start_after_id = next_start_after_id
        start_after = next_start_after

    return all_items


async def _paginate_page(
    fetch_page,
    key: str,
    page_size: int = 100,
    max_pages: int = 100,
) -> list[dict]:
    """Paginate endpoints that support page/limit."""
    all_items: list[dict] = []
    seen_ids: set[str] = set()
    page = 1

    for _ in range(max_pages):
        resp = await fetch_page(page, page_size)
        batch = _extract_items(resp, key)
        if not batch:
            break

        new_count = 0
        for item in batch:
            item_id = item.get("id", item.get("_id", ""))
            if item_id:
                if item_id in seen_ids:
                    continue
                seen_ids.add(item_id)
            all_items.append(item)
            new_count += 1

        # Defensive guard when the API ignores page and returns the same set.
        if new_count == 0:
            break

        total = _extract_total(resp, len(all_items))
        if len(all_items) >= total:
            break

        page += 1

    return all_items


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
        archive_key = location.ghl_location_id or location.slug

        # 1. Import config via snapshot
        from maxlevel.blueprint.engine import snapshot_location
        snap = await snapshot_location(ghl, location_id=lid)
        bp = snap.blueprint

        # 1b. Workflows (raw preservation)
        try:
            workflows_resp = await ghl.workflows.list(location_id=lid)
            workflows_data = workflows_resp.get("workflows", [])
            if not isinstance(workflows_data, list):
                workflows_data = []

            details_by_workflow: dict[str, dict] = {}
            sem = asyncio.Semaphore(10)

            def _extract_id(item: dict) -> str:
                for key in ("id", "_id"):
                    value = item.get(key)
                    if isinstance(value, str) and value:
                        return value
                return ""

            async def _one(wid: str):
                async with sem:
                    try:
                        detail = await ghl.workflows.get(wid)
                    except Exception:
                        return
                    if isinstance(detail, dict):
                        details_by_workflow[wid] = detail

            workflow_ids = [_extract_id(w) for w in workflows_data if isinstance(w, dict)]
            workflow_ids = [wid for wid in workflow_ids if wid]
            await asyncio.gather(*(_one(wid) for wid in workflow_ids))

            write_sync_archive(
                archive_key,
                "workflows",
                {"workflows": workflows_data, "details_by_id": details_by_workflow},
            )

            r = await import_workflows(
                db,
                location,
                [w for w in workflows_data if isinstance(w, dict)],
                details_by_id=details_by_workflow,
            )
            total.created += r.created
            total.updated += r.updated
            total.errors.extend(r.errors)
        except Exception as e:
            total.errors.append(f"Workflows import error: {e}")

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
        try:
            all_contacts = await _paginate_start_after(
                lambda limit, start_after_id, start_after: ghl.contacts.list(
                    location_id=lid,
                    limit=limit,
                    start_after_id=start_after_id,
                    start_after=start_after,
                ),
                key="contacts",
                page_size=100,
            )
        except Exception as e:
            total.errors.append(f"Contact pagination error: {e}")
            all_contacts = []
        write_sync_archive(archive_key, "contacts", {"contacts": all_contacts})

        r, contact_map = await import_contacts(db, location, all_contacts)
        total.created += r.created
        total.updated += r.updated

        # 6b. Notes + Tasks (per-contact; best-effort)
        contact_ids = [cid for cid in contact_map.keys() if isinstance(cid, str) and cid]

        async def _fetch_by_contact(fetch_fn, key: str) -> dict[str, list[dict]]:
            out: dict[str, list[dict]] = {}
            if not contact_ids:
                return out

            sem = asyncio.Semaphore(10)

            async def _one(cid: str) -> tuple[str, list[dict], str | None]:
                async with sem:
                    try:
                        resp = await fetch_fn(cid)
                    except Exception as exc:
                        return cid, [], str(exc)
                    items = resp.get(key, [])
                    if not isinstance(items, list):
                        items = []
                    return cid, [item for item in items if isinstance(item, dict)], None

            batch_size = 100
            for i in range(0, len(contact_ids), batch_size):
                batch = contact_ids[i:i + batch_size]
                results = await asyncio.gather(*(_one(cid) for cid in batch))
                for cid, items, err in results:
                    if err:
                        total.errors.append(f"{key} fetch error for contact {cid}: {err}")
                        continue
                    if items:
                        out[cid] = items

            return out

        try:
            notes_by_contact = await _fetch_by_contact(
                lambda cid: ghl.contacts.get_notes(cid, location_id=lid),
                "notes",
            )
        except Exception as e:
            notes_by_contact = {}
            total.errors.append(f"Notes import error: {e}")

        if notes_by_contact:
            write_sync_archive(archive_key, "notes", notes_by_contact)
            r = await import_notes(db, location, notes_by_contact, contact_map=contact_map)
            total.created += r.created
            total.updated += r.updated
            total.errors.extend(r.errors)

        try:
            tasks_by_contact = await _fetch_by_contact(
                lambda cid: ghl.contacts.get_tasks(cid, location_id=lid),
                "tasks",
            )
        except Exception as e:
            tasks_by_contact = {}
            total.errors.append(f"Tasks import error: {e}")

        if tasks_by_contact:
            write_sync_archive(archive_key, "tasks", tasks_by_contact)
            r = await import_tasks(db, location, tasks_by_contact, contact_map=contact_map)
            total.created += r.created
            total.updated += r.updated
            total.errors.extend(r.errors)

        # 7. Opportunities per pipeline
        opportunities_by_pipeline: dict[str, list[dict]] = {}
        for p_data in pipelines_data:
            p_id = p_data["id"]
            if not p_id:
                continue
            try:
                opps_resp = await ghl.opportunities.list(
                    pipeline_id=p_id, location_id=lid
                )
                opps_list = opps_resp.get("opportunities", [])
                opportunities_by_pipeline[p_id] = opps_list
                r = await import_opportunities(
                    db, location, opps_list, stage_map, contact_map, p_id
                )
                total.created += r.created
                total.updated += r.updated
                total.errors.extend(r.errors)
            except Exception as e:
                total.errors.append(f"Opportunities import error: {e}")
        write_sync_archive(
            archive_key,
            "opportunities",
            {"by_pipeline": opportunities_by_pipeline},
        )

        # 8. Conversations
        try:
            conversations_data = await _paginate_offset(
                lambda limit, offset: ghl.conversations.list(
                    location_id=lid, limit=limit, offset=offset
                ),
                key="conversations",
                page_size=100,
            )
            messages_by_conv: dict[str, list[dict]] = {}
            for conv in conversations_data:
                conv_id = conv.get("id", conv.get("_id", ""))
                if conv_id:
                    try:
                        messages_by_conv[conv_id] = await _paginate_offset(
                            lambda limit, offset: ghl.conversations.messages(
                                conv_id, limit=limit, offset=offset
                            ),
                            key="messages",
                            page_size=100,
                        )
                    except Exception:
                        pass
            r = await import_conversations(db, location, conversations_data, messages_by_conv)
            total.created += r.created
            total.updated += r.updated
            write_sync_archive(
                archive_key,
                "conversations",
                {
                    "conversations": conversations_data,
                    "messages_by_conversation": messages_by_conv,
                },
            )
        except Exception as e:
            total.errors.append(f"Conversations import error: {e}")

        # 9. Calendars
        try:
            cal_resp = await ghl.calendars.list(location_id=lid)
            calendars_data = cal_resp.get("calendars", [])
            details_by_calendar: dict[str, dict] = {}
            appointments_by_calendar: dict[str, list[dict]] = {}
            for cal in calendars_data:
                cal_id = cal.get("id", cal.get("_id", ""))
                if not cal_id:
                    continue
                try:
                    details_by_calendar[cal_id] = await ghl.calendars.get(cal_id)
                except Exception:
                    details_by_calendar[cal_id] = {}
                try:
                    appointments_by_calendar[cal_id] = await _paginate_offset(
                        lambda limit, offset: ghl.calendars.get_appointments(
                            calendar_id=cal_id,
                            location_id=lid,
                            limit=limit,
                            offset=offset,
                        ),
                        key="appointments",
                        page_size=100,
                    )
                except Exception:
                    appointments_by_calendar[cal_id] = []
            r = await import_calendars(
                db,
                location,
                calendars_data,
                appointments_by_calendar,
                details_by_calendar=details_by_calendar,
            )
            total.created += r.created
            total.updated += r.updated
            write_sync_archive(
                archive_key,
                "calendars",
                {
                    "calendars": calendars_data,
                    "details_by_calendar": details_by_calendar,
                    "appointments_by_calendar": appointments_by_calendar,
                },
            )
        except Exception as e:
            total.errors.append(f"Calendars import error: {e}")

        # 10. Forms
        try:
            forms_resp = await ghl.forms.list(location_id=lid)
            forms_data = forms_resp.get("forms", [])
            details_by_form: dict[str, dict] = {}
            submissions_by_form: dict[str, list[dict]] = {}
            for form in forms_data:
                form_id = form.get("id", form.get("_id", ""))
                if form_id:
                    try:
                        details_by_form[form_id] = await ghl.forms.get(form_id)
                    except Exception:
                        details_by_form[form_id] = {}
                    try:
                        submissions_by_form[form_id] = await _paginate_page(
                            lambda page, limit: ghl.forms.submissions(
                                form_id, location_id=lid, limit=limit, page=page
                            ),
                            key="submissions",
                            page_size=100,
                        )
                    except Exception:
                        pass
            r = await import_forms(
                db, location, forms_data, submissions_by_form, details_by_form
            )
            total.created += r.created
            total.updated += r.updated
            write_sync_archive(
                archive_key,
                "forms",
                {
                    "forms": forms_data,
                    "details_by_form": details_by_form,
                    "submissions_by_form": submissions_by_form,
                },
            )
        except Exception as e:
            total.errors.append(f"Forms import error: {e}")

        # 11. Surveys
        try:
            surveys_resp = await ghl.surveys.list(location_id=lid)
            surveys_data = surveys_resp.get("surveys", [])
            details_by_survey: dict[str, dict] = {}
            submissions_by_survey: dict[str, list[dict]] = {}
            for survey in surveys_data:
                survey_id = survey.get("id", survey.get("_id", ""))
                if survey_id:
                    try:
                        details_by_survey[survey_id] = await ghl.surveys.get(survey_id)
                    except Exception:
                        details_by_survey[survey_id] = {}
                    try:
                        submissions_by_survey[survey_id] = await _paginate_page(
                            lambda page, limit: ghl.surveys.submissions(
                                survey_id, location_id=lid, limit=limit, page=page
                            ),
                            key="submissions",
                            page_size=100,
                        )
                    except Exception:
                        pass
            r = await import_surveys(
                db, location, surveys_data, submissions_by_survey, details_by_survey
            )
            total.created += r.created
            total.updated += r.updated
            write_sync_archive(
                archive_key,
                "surveys",
                {
                    "surveys": surveys_data,
                    "details_by_survey": details_by_survey,
                    "submissions_by_survey": submissions_by_survey,
                },
            )
        except Exception as e:
            total.errors.append(f"Surveys import error: {e}")

        # 12. Campaigns
        try:
            camp_resp = await ghl.campaigns.list(location_id=lid)
            campaigns_data = camp_resp.get("campaigns", [])
            details_by_campaign: dict[str, dict] = {}
            for campaign in campaigns_data:
                campaign_id = campaign.get("id", campaign.get("_id", ""))
                if not campaign_id:
                    continue
                try:
                    details_by_campaign[campaign_id] = await ghl.campaigns.get(campaign_id)
                except Exception:
                    details_by_campaign[campaign_id] = {}

            r = await import_campaigns(db, location, campaigns_data, details_by_campaign)
            total.created += r.created
            total.updated += r.updated
            write_sync_archive(
                archive_key,
                "campaigns",
                {
                    "campaigns": campaigns_data,
                    "details_by_campaign": details_by_campaign,
                },
            )
        except Exception as e:
            total.errors.append(f"Campaigns import error: {e}")

        # 13. Funnels
        try:
            funnel_resp = await ghl.funnels.list(location_id=lid)
            funnels_data = funnel_resp.get("funnels", [])
            details_by_funnel: dict[str, dict] = {}
            pages_by_funnel: dict[str, list[dict]] = {}
            page_details_by_funnel: dict[str, dict[str, dict]] = {}
            for funnel in funnels_data:
                funnel_id = funnel.get("id", funnel.get("_id", ""))
                if funnel_id:
                    try:
                        details_by_funnel[funnel_id] = await ghl.funnels.get(funnel_id)
                    except Exception:
                        details_by_funnel[funnel_id] = {}
                    try:
                        pages_by_funnel[funnel_id] = await _paginate_offset(
                            lambda limit, offset: ghl.funnels.pages(
                                funnel_id,
                                location_id=lid,
                                limit=limit,
                                offset=offset,
                            ),
                            key="pages",
                            page_size=100,
                        )
                    except Exception:
                        pages_by_funnel[funnel_id] = []

                    details_for_pages: dict[str, dict] = {}
                    for page in pages_by_funnel[funnel_id]:
                        page_id = page.get("id", page.get("_id", ""))
                        if not page_id:
                            continue
                        try:
                            details_for_pages[page_id] = await ghl.funnels.get_page(
                                funnel_id, page_id
                            )
                        except Exception:
                            details_for_pages[page_id] = {}
                    page_details_by_funnel[funnel_id] = details_for_pages

            r = await import_funnels(
                db,
                location,
                funnels_data,
                pages_by_funnel,
                details_by_funnel=details_by_funnel,
                page_details_by_funnel=page_details_by_funnel,
            )
            total.created += r.created
            total.updated += r.updated
            write_sync_archive(
                archive_key,
                "funnels",
                {
                    "funnels": funnels_data,
                    "details_by_funnel": details_by_funnel,
                    "pages_by_funnel": pages_by_funnel,
                    "page_details_by_funnel": page_details_by_funnel,
                },
            )
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

        # 1b. Custom fields + custom values (prereqs for contacts/opportunities customFields)
        r = await export_custom_fields(db, location, ghl)
        total.created += r.created
        total.updated += r.updated
        total.skipped += r.skipped
        total.errors.extend(r.errors)

        r = await export_custom_values(db, location, ghl)
        total.created += r.created
        total.updated += r.updated
        total.skipped += r.skipped
        total.errors.extend(r.errors)

        # 2. Contacts
        r = await export_contacts(db, location, ghl)
        total.created += r.created
        total.updated += r.updated
        total.errors.extend(r.errors)

        # 2b. Notes + Tasks (best-effort, create-only)
        r = await export_notes(db, location, ghl)
        total.created += r.created
        total.updated += r.updated
        total.skipped += r.skipped
        total.errors.extend(r.errors)

        r = await export_tasks(db, location, ghl)
        total.created += r.created
        total.updated += r.updated
        total.skipped += r.skipped
        total.errors.extend(r.errors)

        # 2c. Pipelines/stages (browser-backed export; prerequisite for opportunities)
        if settings.sync_browser_fallback_enabled:
            r = await export_browser_backed_resources(
                db,
                location,
                tab_id=settings.sync_browser_tab_id,
                domains={"pipelines"},
                execute=settings.sync_browser_execute_enabled,
                profile_name=settings.sync_browser_profile,
                headless=settings.sync_browser_headless,
                continue_on_error=settings.sync_browser_continue_on_error,
                max_find_attempts=settings.sync_browser_find_attempts,
                retry_wait_seconds=settings.sync_browser_step_retry_wait_seconds,
                require_login=settings.sync_browser_require_login,
                preflight_url=settings.sync_browser_preflight_url,
                login_email=settings.sync_browser_login_email,
                login_password=settings.sync_browser_login_password,
                login_timeout_seconds=settings.sync_browser_login_timeout_seconds,
                ghl=ghl,
            )
            total.created += r.created
            total.updated += r.updated
            total.skipped += r.skipped
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

        # 5b. Workflows (browser-backed rebuild; best-effort)
        if settings.sync_browser_fallback_enabled:
            r = await export_workflows_via_browser(
                db,
                location,
                ghl,
                tab_id=settings.sync_browser_tab_id,
                fidelity=settings.sync_workflow_fidelity,
                execute=settings.sync_browser_execute_enabled,
                profile_name=settings.sync_browser_profile,
                headless=settings.sync_browser_headless,
                continue_on_error=settings.sync_browser_continue_on_error,
                max_find_attempts=settings.sync_browser_find_attempts,
                retry_wait_seconds=settings.sync_browser_step_retry_wait_seconds,
                require_login=settings.sync_browser_require_login,
                preflight_url=settings.sync_browser_preflight_url,
                login_email=settings.sync_browser_login_email,
                login_password=settings.sync_browser_login_password,
                login_timeout_seconds=settings.sync_browser_login_timeout_seconds,
            )
            total.created += r.created
            total.updated += r.updated
            total.skipped += r.skipped
            total.errors.extend(r.errors)

        # 6. Browser-backed fallback for API-limited resources
        if settings.sync_browser_fallback_enabled:
            r = await export_browser_backed_resources(
                db,
                location,
                tab_id=settings.sync_browser_tab_id,
                domains={"forms", "surveys", "campaigns", "funnels"},
                execute=settings.sync_browser_execute_enabled,
                profile_name=settings.sync_browser_profile,
                headless=settings.sync_browser_headless,
                continue_on_error=settings.sync_browser_continue_on_error,
                max_find_attempts=settings.sync_browser_find_attempts,
                retry_wait_seconds=settings.sync_browser_step_retry_wait_seconds,
                require_login=settings.sync_browser_require_login,
                preflight_url=settings.sync_browser_preflight_url,
                login_email=settings.sync_browser_login_email,
                login_password=settings.sync_browser_login_password,
                login_timeout_seconds=settings.sync_browser_login_timeout_seconds,
                ghl=ghl,
            )
            total.created += r.created
            total.updated += r.updated
            total.skipped += r.skipped
            total.errors.extend(r.errors)

    return total
