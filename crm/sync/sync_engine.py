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

    return total
