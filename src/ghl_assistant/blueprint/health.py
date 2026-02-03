"""Location health checks - independent of blueprints."""

from __future__ import annotations

from typing import Any

from .models import LocationBlueprint


def check_health(blueprint: LocationBlueprint) -> dict[str, Any]:
    """Run health checks against a location's snapshotted blueprint.

    Returns a dict of check_name -> {passed: bool, detail: str}.
    """
    checks: dict[str, Any] = {}

    # Has tags?
    checks["Has tags"] = {
        "passed": len(blueprint.tags) > 0,
        "detail": f"{len(blueprint.tags)} tags" if blueprint.tags else "No tags configured",
    }

    # Has custom fields?
    checks["Has custom fields"] = {
        "passed": len(blueprint.custom_fields) > 0,
        "detail": (
            f"{len(blueprint.custom_fields)} fields"
            if blueprint.custom_fields
            else "No custom fields"
        ),
    }

    # Has active workflows?
    active = [w for w in blueprint.workflows if w.status == "published"]
    checks["Has active workflows"] = {
        "passed": len(active) > 0,
        "detail": (
            f"{len(active)} published, {len(blueprint.workflows)} total"
            if blueprint.workflows
            else "No workflows"
        ),
    }

    # Has calendars?
    checks["Has calendars"] = {
        "passed": len(blueprint.calendars) > 0,
        "detail": (
            f"{len(blueprint.calendars)} calendars"
            if blueprint.calendars
            else "No calendars configured"
        ),
    }

    # Has pipelines with 2+ stages?
    good_pipelines = [p for p in blueprint.pipelines if len(p.stages) >= 2]
    checks["Has pipelines with 2+ stages"] = {
        "passed": len(good_pipelines) > 0,
        "detail": (
            f"{len(good_pipelines)} pipelines with 2+ stages"
            if good_pipelines
            else "No pipelines with multiple stages"
        ),
    }

    # Custom values non-empty?
    non_empty = [cv for cv in blueprint.custom_values if cv.value.strip()]
    checks["Custom values populated"] = {
        "passed": len(non_empty) == len(blueprint.custom_values) if blueprint.custom_values else True,
        "detail": (
            f"{len(non_empty)}/{len(blueprint.custom_values)} populated"
            if blueprint.custom_values
            else "No custom values"
        ),
    }

    # Has forms?
    checks["Has forms"] = {
        "passed": len(blueprint.forms) > 0,
        "detail": (
            f"{len(blueprint.forms)} forms"
            if blueprint.forms
            else "No forms configured"
        ),
    }

    # Has funnels?
    checks["Has funnels"] = {
        "passed": len(blueprint.funnels) > 0,
        "detail": (
            f"{len(blueprint.funnels)} funnels"
            if blueprint.funnels
            else "No funnels configured"
        ),
    }

    return checks


def health_score(checks: dict[str, Any]) -> float:
    """Compute an overall health score from check results."""
    if not checks:
        return 0.0
    passed = sum(1 for c in checks.values() if c.get("passed", False))
    return passed / len(checks) * 100
