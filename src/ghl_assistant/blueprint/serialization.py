"""Blueprint serialization - YAML read/write for LocationBlueprint."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

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
    SurveySpec,
    TagSpec,
    WorkflowSpec,
)


def _blueprint_to_dict(bp: LocationBlueprint) -> dict[str, Any]:
    """Convert a LocationBlueprint to a serializable dict."""
    d: dict[str, Any] = {
        "blueprint": {
            "name": bp.metadata.name,
            "version": bp.metadata.version,
            "description": bp.metadata.description,
            "source_location_id": bp.metadata.source_location_id,
            "created_at": bp.metadata.created_at,
        },
    }

    if bp.tags:
        d["tags"] = [{"name": t.name} for t in bp.tags]

    if bp.custom_fields:
        d["custom_fields"] = []
        for cf in bp.custom_fields:
            cf_entry: dict[str, Any] = {
                "name": cf.name,
                "field_key": cf.field_key,
                "data_type": cf.data_type,
            }
            if cf.placeholder:
                cf_entry["placeholder"] = cf.placeholder
            if cf.position is not None:
                cf_entry["position"] = cf.position
            d["custom_fields"].append(cf_entry)

    if bp.custom_values:
        d["custom_values"] = [{"name": cv.name, "value": cv.value} for cv in bp.custom_values]

    if bp.pipelines:
        d["pipelines"] = []
        for p in bp.pipelines:
            p_entry: dict[str, Any] = {"name": p.name}
            if p.stages:
                stages_list = []
                for s in p.stages:
                    s_entry: dict[str, Any] = {"name": s.name}
                    if s.position is not None:
                        s_entry["position"] = s.position
                    stages_list.append(s_entry)
                p_entry["stages"] = stages_list
            d["pipelines"].append(p_entry)

    if bp.workflows:
        d["workflows"] = [{"name": w.name, "status": w.status} for w in bp.workflows]

    if bp.calendars:
        d["calendars"] = []
        for c in bp.calendars:
            cal_entry: dict[str, Any] = {"name": c.name}
            if c.event_type:
                cal_entry["event_type"] = c.event_type
            d["calendars"].append(cal_entry)

    if bp.forms:
        d["forms"] = [{"name": f.name} for f in bp.forms]

    if bp.surveys:
        d["surveys"] = [{"name": s.name} for s in bp.surveys]

    if bp.campaigns:
        d["campaigns"] = []
        for c in bp.campaigns:
            camp_entry: dict[str, Any] = {"name": c.name}
            if c.status:
                camp_entry["status"] = c.status
            d["campaigns"].append(camp_entry)

    if bp.funnels:
        d["funnels"] = []
        for f in bp.funnels:
            fun_entry: dict[str, Any] = {"name": f.name}
            if f.steps:
                fun_entry["steps"] = f.steps
            d["funnels"].append(fun_entry)

    return d


def _dict_to_blueprint(d: dict[str, Any]) -> LocationBlueprint:
    """Convert a parsed YAML dict to a LocationBlueprint."""
    bp_meta = d.get("blueprint", {})
    metadata = BlueprintMetadata(
        name=bp_meta.get("name", "Unnamed Blueprint"),
        version=bp_meta.get("version", 1),
        description=bp_meta.get("description", ""),
        source_location_id=bp_meta.get("source_location_id"),
        created_at=bp_meta.get("created_at", ""),
    )

    tags = [TagSpec(name=t["name"]) for t in d.get("tags", [])]

    custom_fields = [
        CustomFieldSpec(
            name=cf["name"],
            field_key=cf["field_key"],
            data_type=cf.get("data_type", "TEXT"),
            placeholder=cf.get("placeholder"),
            position=cf.get("position"),
        )
        for cf in d.get("custom_fields", [])
    ]

    custom_values = [
        CustomValueSpec(name=cv["name"], value=cv["value"])
        for cv in d.get("custom_values", [])
    ]

    pipelines = [
        PipelineSpec(
            name=p["name"],
            stages=[
                PipelineStageSpec(name=s["name"], position=s.get("position"))
                for s in p.get("stages", [])
            ],
        )
        for p in d.get("pipelines", [])
    ]

    workflows = [
        WorkflowSpec(name=w["name"], status=w.get("status", "draft"))
        for w in d.get("workflows", [])
    ]

    calendars = [
        CalendarSpec(name=c["name"], event_type=c.get("event_type"))
        for c in d.get("calendars", [])
    ]

    forms = [FormSpec(name=f["name"]) for f in d.get("forms", [])]
    surveys = [SurveySpec(name=s["name"]) for s in d.get("surveys", [])]

    campaigns = [
        CampaignSpec(name=c["name"], status=c.get("status"))
        for c in d.get("campaigns", [])
    ]

    funnels = [
        FunnelSpec(name=f["name"], steps=f.get("steps", []))
        for f in d.get("funnels", [])
    ]

    return LocationBlueprint(
        metadata=metadata,
        tags=tags,
        custom_fields=custom_fields,
        custom_values=custom_values,
        pipelines=pipelines,
        workflows=workflows,
        calendars=calendars,
        forms=forms,
        surveys=surveys,
        campaigns=campaigns,
        funnels=funnels,
    )


def save_blueprint(blueprint: LocationBlueprint, path: str | Path) -> Path:
    """Save a LocationBlueprint to a YAML file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _blueprint_to_dict(blueprint)
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    return path


def load_blueprint(path: str | Path) -> LocationBlueprint:
    """Load a LocationBlueprint from a YAML file."""
    path = Path(path)
    with open(path) as f:
        data = yaml.safe_load(f)
    if not data:
        raise ValueError(f"Empty or invalid blueprint file: {path}")
    if not isinstance(data, dict):
        raise ValueError(f"Blueprint file must contain a YAML mapping, got {type(data).__name__}: {path}")
    return _dict_to_blueprint(data)
