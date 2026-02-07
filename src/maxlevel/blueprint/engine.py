"""Blueprint engine - Snapshot, provision, audit, and bulk operations."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TYPE_CHECKING

from .models import (
    BlueprintMetadata,
    CalendarSpec,
    CampaignSpec,
    CustomFieldSpec,
    CustomValueSpec,
    FormSpec,
    FunnelSpec,
    LocationBlueprint,
    PipelineSpec,
    PipelineStageSpec,
    ResourceAccess,
    RESOURCE_ACCESS,
    SurveySpec,
    TagSpec,
    WorkflowSpec,
)
from .serialization import save_blueprint

if TYPE_CHECKING:
    from ..api.client import GHLClient


@dataclass
class SnapshotResult:
    """Result of snapshotting a location, including ID mappings."""
    blueprint: LocationBlueprint
    id_map: dict[str, dict[str, str]] = field(default_factory=dict)
    """Maps resource_type -> {name_or_key: ghl_id}"""
    warnings: list[str] = field(default_factory=list)
    """Warnings about API calls that failed during snapshot."""


@dataclass
class ProvisionAction:
    resource_type: str
    name: str
    action: str  # CREATE, UPDATE, OK, EXTRA, MANUAL
    details: str = ""
    ghl_id: str | None = None
    spec: Any = None  # The desired *Spec dataclass for CREATE/UPDATE actions


@dataclass
class ProvisionResult:
    actions: list[ProvisionAction] = field(default_factory=list)
    created: int = 0
    updated: int = 0
    skipped: int = 0
    manual: int = 0
    errors: list[str] = field(default_factory=list)


async def snapshot_location(
    ghl: GHLClient,
    name: str = "Location Blueprint",
    location_id: str | None = None,
) -> SnapshotResult:
    """Snapshot a location's configuration into a LocationBlueprint.

    Fires all API list calls concurrently and transforms responses into specs.
    """
    lid = location_id or ghl.config.location_id

    # Fire all API calls concurrently
    results = await asyncio.gather(
        ghl.tags.list(location_id=lid),
        ghl.custom_fields.list(location_id=lid),
        ghl.custom_values.list(location_id=lid),
        ghl.opportunities.pipelines(location_id=lid),
        ghl.workflows.list(location_id=lid),
        ghl.calendars.list(location_id=lid),
        ghl.forms.list(location_id=lid),
        ghl.surveys.list(location_id=lid),
        ghl.campaigns.list(location_id=lid),
        ghl.funnels.list(location_id=lid),
        return_exceptions=True,
    )

    (
        tags_resp, fields_resp, values_resp, pipelines_resp,
        workflows_resp, calendars_resp, forms_resp, surveys_resp,
        campaigns_resp, funnels_resp,
    ) = results

    # Track warnings for failed API calls
    warnings: list[str] = []
    api_names = [
        "tags", "custom_fields", "custom_values", "pipelines",
        "workflows", "calendars", "forms", "surveys", "campaigns", "funnels",
    ]
    for resp, api_name in zip(results, api_names):
        if isinstance(resp, Exception):
            warnings.append(f"Failed to fetch {api_name}: {resp}")

    id_map: dict[str, dict[str, str]] = {}

    # Transform tags
    tags: list[TagSpec] = []
    id_map["tags"] = {}
    if isinstance(tags_resp, dict):
        for t in tags_resp.get("tags", []):
            tags.append(TagSpec(name=t["name"]))
            id_map["tags"][t["name"]] = t.get("_id", t.get("id", ""))

    # Transform custom fields
    custom_fields: list[CustomFieldSpec] = []
    id_map["custom_fields"] = {}
    if isinstance(fields_resp, dict):
        for cf in fields_resp.get("customFields", []):
            custom_fields.append(CustomFieldSpec(
                name=cf.get("name", ""),
                field_key=cf.get("fieldKey", ""),
                data_type=cf.get("dataType", "TEXT"),
                placeholder=cf.get("placeholder"),
                position=cf.get("position"),
            ))
            id_map["custom_fields"][cf.get("fieldKey", "")] = cf.get("id", "")

    # Transform custom values
    custom_values: list[CustomValueSpec] = []
    id_map["custom_values"] = {}
    if isinstance(values_resp, dict):
        for cv in values_resp.get("customValues", []):
            custom_values.append(CustomValueSpec(
                name=cv.get("name", ""),
                value=cv.get("value", ""),
            ))
            id_map["custom_values"][cv.get("name", "")] = cv.get("id", "")

    # Transform pipelines
    pipelines: list[PipelineSpec] = []
    id_map["pipelines"] = {}
    if isinstance(pipelines_resp, dict):
        for p in pipelines_resp.get("pipelines", []):
            stages = [
                PipelineStageSpec(name=s.get("name", ""), position=s.get("position"))
                for s in p.get("stages", [])
            ]
            pipelines.append(PipelineSpec(name=p.get("name", ""), stages=stages))
            id_map["pipelines"][p.get("name", "")] = p.get("id", p.get("_id", ""))

    # Transform workflows
    workflows: list[WorkflowSpec] = []
    id_map["workflows"] = {}
    if isinstance(workflows_resp, dict):
        for w in workflows_resp.get("workflows", []):
            workflows.append(WorkflowSpec(
                name=w.get("name", ""),
                status=w.get("status", "draft"),
            ))
            id_map["workflows"][w.get("name", "")] = w.get("id", w.get("_id", ""))

    # Transform calendars
    calendars: list[CalendarSpec] = []
    id_map["calendars"] = {}
    if isinstance(calendars_resp, dict):
        for c in calendars_resp.get("calendars", []):
            calendars.append(CalendarSpec(
                name=c.get("name", ""),
                event_type=c.get("eventType"),
            ))
            id_map["calendars"][c.get("name", "")] = c.get("id", c.get("_id", ""))

    # Transform forms
    forms: list[FormSpec] = []
    id_map["forms"] = {}
    if isinstance(forms_resp, dict):
        for f in forms_resp.get("forms", []):
            forms.append(FormSpec(name=f.get("name", "")))
            id_map["forms"][f.get("name", "")] = f.get("_id", f.get("id", ""))

    # Transform surveys
    surveys: list[SurveySpec] = []
    id_map["surveys"] = {}
    if isinstance(surveys_resp, dict):
        for s in surveys_resp.get("surveys", []):
            surveys.append(SurveySpec(name=s.get("name", "")))
            id_map["surveys"][s.get("name", "")] = s.get("_id", s.get("id", ""))

    # Transform campaigns
    campaigns_list: list[CampaignSpec] = []
    id_map["campaigns"] = {}
    if isinstance(campaigns_resp, dict):
        for c in campaigns_resp.get("campaigns", []):
            campaigns_list.append(CampaignSpec(
                name=c.get("name", ""),
                status=c.get("status"),
            ))
            id_map["campaigns"][c.get("name", "")] = c.get("id", c.get("_id", ""))

    # Transform funnels
    funnels: list[FunnelSpec] = []
    id_map["funnels"] = {}
    if isinstance(funnels_resp, dict):
        for f in funnels_resp.get("funnels", []):
            steps = [s.get("name", "") for s in f.get("steps", [])]
            funnels.append(FunnelSpec(name=f.get("name", ""), steps=steps))
            id_map["funnels"][f.get("name", "")] = f.get("_id", f.get("id", ""))

    blueprint = LocationBlueprint(
        metadata=BlueprintMetadata(
            name=name,
            source_location_id=lid,
        ),
        tags=tags,
        custom_fields=custom_fields,
        custom_values=custom_values,
        pipelines=pipelines,
        workflows=workflows,
        calendars=calendars,
        forms=forms,
        surveys=surveys,
        campaigns=campaigns_list,
        funnels=funnels,
    )

    return SnapshotResult(blueprint=blueprint, id_map=id_map, warnings=warnings)


async def provision_location(
    ghl: GHLClient,
    blueprint: LocationBlueprint,
    location_id: str | None = None,
    dry_run: bool = True,
) -> ProvisionResult:
    """Apply a blueprint to a location.

    If dry_run=True (default), computes the plan without making changes.
    If dry_run=False, executes creates/updates via the API.
    """
    from .diff import compute_plan

    lid = location_id or ghl.config.location_id
    plan = await compute_plan(ghl, blueprint, location_id=lid)

    if dry_run:
        return plan

    result = ProvisionResult()

    for action in plan.actions:
        if action.action == "CREATE" and RESOURCE_ACCESS.get(action.resource_type) == ResourceAccess.FULL_CRUD:
            try:
                await _create_resource(ghl, action, lid)
                result.created += 1
                action.action = "CREATED"
            except Exception as e:
                result.errors.append(f"Failed to create {action.resource_type}/{action.name}: {e}")
        elif action.action == "UPDATE" and RESOURCE_ACCESS.get(action.resource_type) == ResourceAccess.FULL_CRUD:
            try:
                await _update_resource(ghl, action, lid)
                result.updated += 1
                action.action = "UPDATED"
            except Exception as e:
                result.errors.append(f"Failed to update {action.resource_type}/{action.name}: {e}")
        elif action.action == "MANUAL":
            result.manual += 1
        else:
            result.skipped += 1

        result.actions.append(action)

    return result


async def _create_resource(
    ghl: GHLClient,
    action: ProvisionAction,
    location_id: str | None,
) -> None:
    """Create a single resource via the API."""
    spec = action.spec
    if action.resource_type == "tags":
        await ghl.tags.create(name=action.name, location_id=location_id)
    elif action.resource_type == "custom_fields" and isinstance(spec, CustomFieldSpec):
        await ghl.custom_fields.create(
            name=spec.name,
            field_key=spec.field_key,
            data_type=spec.data_type,
            placeholder=spec.placeholder,
            location_id=location_id,
        )
    elif action.resource_type == "custom_values" and isinstance(spec, CustomValueSpec):
        await ghl.custom_values.create(
            name=spec.name,
            value=spec.value,
            location_id=location_id,
        )


async def _update_resource(
    ghl: GHLClient,
    action: ProvisionAction,
    location_id: str | None,
) -> None:
    """Update a single resource via the API."""
    if not action.ghl_id or not action.spec:
        return

    spec = action.spec
    if action.resource_type == "custom_fields" and isinstance(spec, CustomFieldSpec):
        await ghl.custom_fields.update(
            field_id=action.ghl_id,
            name=spec.name,
            placeholder=spec.placeholder,
            position=spec.position,
            location_id=location_id,
        )
    elif action.resource_type == "custom_values" and isinstance(spec, CustomValueSpec):
        await ghl.custom_values.update(
            value_id=action.ghl_id,
            name=spec.name,
            value=spec.value,
            location_id=location_id,
        )
    elif action.resource_type == "tags":
        await ghl.tags.update(tag_id=action.ghl_id, name=action.name)


@dataclass
class AuditResult:
    plan: ProvisionResult
    health: dict[str, Any] | None = None
    compliance_score: float = 0.0
    total_resources: int = 0
    matched_resources: int = 0


async def audit_location(
    ghl: GHLClient,
    blueprint: LocationBlueprint,
    location_id: str | None = None,
    run_health: bool = True,
) -> AuditResult:
    """Audit a location against a blueprint and optionally run health checks."""
    from .diff import compute_plan
    from .health import check_health

    lid = location_id or ghl.config.location_id
    plan = await compute_plan(ghl, blueprint, location_id=lid)

    total = 0
    matched = 0
    for action in plan.actions:
        if action.action != "EXTRA":
            total += 1
        if action.action == "OK":
            matched += 1

    score = (matched / total * 100) if total > 0 else 0.0

    health_result = None
    if run_health:
        snapshot_res = await snapshot_location(ghl, location_id=lid)
        health_result = check_health(snapshot_res.blueprint)

    return AuditResult(
        plan=plan,
        health=health_result,
        compliance_score=score,
        total_resources=total,
        matched_resources=matched,
    )


async def bulk_snapshot(
    ghl: GHLClient,
    output_dir: str = "./blueprints",
) -> list[tuple[str, str]]:
    """Snapshot all locations under the company. Returns list of (location_name, file_path)."""
    locations_resp = await ghl.search_locations()
    locations = locations_resp.get("locations", [])
    results: list[tuple[str, str]] = []
    output_path = Path(output_dir)

    for loc in locations:
        loc_id = loc.get("_id", loc.get("id", ""))
        loc_name = loc.get("name", "unnamed")
        slug = loc_name.lower().replace(" ", "_").replace("/", "_")[:50]

        try:
            snapshot_res = await snapshot_location(ghl, name=loc_name, location_id=loc_id)
            filepath = save_blueprint(snapshot_res.blueprint, output_path / f"{slug}.yaml")
            results.append((loc_name, str(filepath)))
        except Exception as e:
            results.append((loc_name, f"ERROR: {e}"))

    return results


async def bulk_audit(
    ghl: GHLClient,
    blueprint: LocationBlueprint,
) -> list[tuple[str, AuditResult]]:
    """Audit all locations under the company against a blueprint."""
    locations_resp = await ghl.search_locations()
    locations = locations_resp.get("locations", [])
    results: list[tuple[str, AuditResult]] = []

    for loc in locations:
        loc_id = loc.get("_id", loc.get("id", ""))
        loc_name = loc.get("name", "unnamed")
        try:
            result = await audit_location(ghl, blueprint, location_id=loc_id)
            results.append((loc_name, result))
        except Exception as e:
            # Create a failed audit result
            failed = AuditResult(
                plan=ProvisionResult(errors=[str(e)]),
                compliance_score=0.0,
            )
            results.append((loc_name, failed))

    return results
