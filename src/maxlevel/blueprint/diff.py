"""Blueprint diff - Terraform-style plan computation and Rich rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .models import (
    LocationBlueprint,
    ResourceAccess,
    RESOURCE_ACCESS,
)
from .engine import ProvisionAction, ProvisionResult, snapshot_location

if TYPE_CHECKING:
    from ..api.client import GHLClient


def _identity_key(resource_type: str, spec) -> str:
    """Get the identity key for matching resources.

    Custom fields use field_key; everything else uses name.
    """
    if resource_type == "custom_fields" and hasattr(spec, "field_key"):
        return spec.field_key
    return spec.name


def _match_resources(
    resource_type: str,
    desired: list,
    live: list,
    live_id_map: dict[str, str],
) -> list[ProvisionAction]:
    """Match desired resources against live resources and classify each."""
    actions: list[ProvisionAction] = []
    access = RESOURCE_ACCESS.get(resource_type, ResourceAccess.READ_ONLY)

    # Build lookup from live resources by identity key
    live_by_key: dict[str, object] = {}
    for item in live:
        key = _identity_key(resource_type, item)
        live_by_key[key] = item

    # Check each desired resource
    matched_keys: set[str] = set()
    for spec in desired:
        key = _identity_key(resource_type, spec)
        matched_keys.add(key)

        if key in live_by_key:
            live_item = live_by_key[key]
            drift = _detect_drift(resource_type, spec, live_item)
            if drift:
                if access == ResourceAccess.FULL_CRUD:
                    actions.append(ProvisionAction(
                        resource_type=resource_type,
                        name=key,
                        action="UPDATE",
                        details=drift,
                        ghl_id=live_id_map.get(key),
                        spec=spec,
                    ))
                else:
                    actions.append(ProvisionAction(
                        resource_type=resource_type,
                        name=key,
                        action="MANUAL",
                        details=f"drift detected: {drift}",
                    ))
            else:
                actions.append(ProvisionAction(
                    resource_type=resource_type,
                    name=key,
                    action="OK",
                ))
        else:
            if access == ResourceAccess.FULL_CRUD:
                details = _display_details(resource_type, spec)
                actions.append(ProvisionAction(
                    resource_type=resource_type,
                    name=key,
                    action="CREATE",
                    details=details,
                    spec=spec,
                ))
            else:
                actions.append(ProvisionAction(
                    resource_type=resource_type,
                    name=spec.name,
                    action="MANUAL",
                    details="missing — requires manual setup",
                ))

    # Find extras (exist in live but not in blueprint)
    for key, item in live_by_key.items():
        if key not in matched_keys:
            actions.append(ProvisionAction(
                resource_type=resource_type,
                name=item.name if hasattr(item, "name") else key,
                action="EXTRA",
                details="exists in location but not in blueprint",
            ))

    return actions


def _detect_drift(resource_type: str, desired, live) -> str:
    """Compare desired vs live spec and return drift description, or empty string if matched."""
    diffs: list[str] = []

    if resource_type == "custom_fields":
        if hasattr(desired, "data_type") and hasattr(live, "data_type"):
            if desired.data_type != live.data_type:
                diffs.append(f"data_type: {live.data_type} -> {desired.data_type}")
        if hasattr(desired, "name") and hasattr(live, "name"):
            if desired.name != live.name:
                diffs.append(f"name: {live.name} -> {desired.name}")

    elif resource_type == "custom_values":
        if hasattr(desired, "value") and hasattr(live, "value"):
            if desired.value != live.value:
                diffs.append(f"value: {live.value!r} -> {desired.value!r}")

    elif resource_type == "workflows":
        if hasattr(desired, "status") and hasattr(live, "status"):
            if desired.status != live.status:
                diffs.append(f"status: {live.status} -> {desired.status}")

    elif resource_type == "pipelines":
        if hasattr(desired, "stages") and hasattr(live, "stages"):
            desired_names = [s.name for s in desired.stages]
            live_names = [s.name for s in live.stages]
            if desired_names != live_names:
                diffs.append(f"stages differ")

    return ", ".join(diffs)


def _display_details(resource_type: str, spec) -> str:
    """Build a human-readable details string for display in the plan output."""
    if resource_type == "custom_fields":
        return f"{spec.data_type} field"
    elif resource_type == "custom_values":
        val = spec.value[:40] + "..." if len(spec.value) > 40 else spec.value
        return f"value={val!r}"
    return ""


async def compute_plan(
    ghl: GHLClient,
    blueprint: LocationBlueprint,
    location_id: str | None = None,
) -> ProvisionResult:
    """Compute the full provision/audit plan by diffing blueprint against live location."""
    live_snapshot = await snapshot_location(ghl, location_id=location_id)
    live_bp = live_snapshot.blueprint
    id_map = live_snapshot.id_map

    all_actions: list[ProvisionAction] = []

    resource_pairs = [
        ("tags", blueprint.tags, live_bp.tags),
        ("custom_fields", blueprint.custom_fields, live_bp.custom_fields),
        ("custom_values", blueprint.custom_values, live_bp.custom_values),
        ("pipelines", blueprint.pipelines, live_bp.pipelines),
        ("workflows", blueprint.workflows, live_bp.workflows),
        ("calendars", blueprint.calendars, live_bp.calendars),
        ("forms", blueprint.forms, live_bp.forms),
        ("surveys", blueprint.surveys, live_bp.surveys),
        ("campaigns", blueprint.campaigns, live_bp.campaigns),
        ("funnels", blueprint.funnels, live_bp.funnels),
    ]

    for rtype, desired, live in resource_pairs:
        actions = _match_resources(rtype, desired, live, id_map.get(rtype, {}))
        all_actions.extend(actions)

    created = sum(1 for a in all_actions if a.action == "CREATE")
    updated = sum(1 for a in all_actions if a.action == "UPDATE")
    skipped = sum(1 for a in all_actions if a.action in ("OK", "EXTRA"))
    manual = sum(1 for a in all_actions if a.action == "MANUAL")

    return ProvisionResult(
        actions=all_actions,
        created=created,
        updated=updated,
        skipped=skipped,
        manual=manual,
    )


# ============================================================================
# Rich rendering
# ============================================================================

ACTION_STYLES = {
    "CREATE": ("+ ", "green"),
    "CREATED": ("+ ", "green"),
    "UPDATE": ("~ ", "yellow"),
    "UPDATED": ("~ ", "yellow"),
    "OK": ("= ", "dim"),
    "EXTRA": ("? ", "cyan"),
    "MANUAL": ("! ", "red"),
}


def render_plan(plan: ProvisionResult, console: Console | None = None) -> None:
    """Render a terraform-style plan to the console."""
    if console is None:
        console = Console()

    # Group actions by resource type
    by_type: dict[str, list[ProvisionAction]] = {}
    for action in plan.actions:
        by_type.setdefault(action.resource_type, []).append(action)

    console.print()
    console.print(Panel(
        "[bold]Location Blueprint Plan[/bold]\n"
        "Actions to reconcile location with blueprint:",
        style="blue",
    ))
    console.print()

    for rtype, actions in by_type.items():
        access = RESOURCE_ACCESS.get(rtype, ResourceAccess.READ_ONLY)
        access_label = "auto" if access == ResourceAccess.FULL_CRUD else "manual"

        console.print(f"  [bold]{rtype}[/bold] [dim]({access_label})[/dim]")

        for action in actions:
            prefix, style = ACTION_STYLES.get(action.action, ("  ", "white"))
            line = Text()
            line.append(f"    {prefix}", style=style)
            line.append(f"{action.name}", style=style)
            if action.details:
                line.append(f"  ({action.details})", style="dim")
            console.print(line)

        console.print()

    # Summary
    summary_parts = []
    if plan.created:
        summary_parts.append(f"[green]{plan.created} to create[/green]")
    if plan.updated:
        summary_parts.append(f"[yellow]{plan.updated} to update[/yellow]")
    if plan.manual:
        summary_parts.append(f"[red]{plan.manual} need manual setup[/red]")

    ok_count = sum(1 for a in plan.actions if a.action in ("OK",))
    extra_count = sum(1 for a in plan.actions if a.action == "EXTRA")
    if ok_count:
        summary_parts.append(f"[dim]{ok_count} OK[/dim]")
    if extra_count:
        summary_parts.append(f"[cyan]{extra_count} extra[/cyan]")

    console.print(f"  Plan: {', '.join(summary_parts)}")
    console.print()


def render_audit(
    plan: ProvisionResult,
    health: dict | None = None,
    compliance_score: float = 0.0,
    console: Console | None = None,
) -> None:
    """Render audit results including plan + health checks + compliance score."""
    if console is None:
        console = Console()

    render_plan(plan, console)

    # Health checks
    if health:
        console.print(Panel("[bold]Location Health Checks[/bold]", style="blue"))
        console.print()

        table = Table(show_header=True)
        table.add_column("Check", style="cyan", min_width=30)
        table.add_column("Status", justify="center", width=8)
        table.add_column("Detail", style="dim")

        for check_name, check_result in health.items():
            passed = check_result.get("passed", False)
            status = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
            detail = check_result.get("detail", "")
            table.add_row(check_name, status, detail)

        console.print(table)
        console.print()

    # Compliance score
    score_style = "green" if compliance_score >= 80 else "yellow" if compliance_score >= 50 else "red"
    console.print(
        Panel(
            f"[bold]Compliance Score: [{score_style}]{compliance_score:.0f}%[/{score_style}][/bold]",
            style=score_style,
        )
    )


def render_bulk_audit(
    results: list[tuple[str, object]],
    console: Console | None = None,
) -> None:
    """Render a summary table of bulk audit results."""
    if console is None:
        console = Console()

    table = Table(title="Bulk Audit Summary", show_header=True)
    table.add_column("Location", style="cyan", min_width=20)
    table.add_column("Score", justify="right", width=8)
    table.add_column("Create", justify="right", style="green", width=8)
    table.add_column("Update", justify="right", style="yellow", width=8)
    table.add_column("Manual", justify="right", style="red", width=8)
    table.add_column("OK", justify="right", style="dim", width=8)

    for loc_name, audit_result in results:
        score = audit_result.compliance_score
        score_style = "green" if score >= 80 else "yellow" if score >= 50 else "red"
        ok_count = sum(1 for a in audit_result.plan.actions if a.action == "OK")

        table.add_row(
            loc_name,
            f"[{score_style}]{score:.0f}%[/{score_style}]",
            str(audit_result.plan.created),
            str(audit_result.plan.updated),
            str(audit_result.plan.manual),
            str(ok_count),
        )

    console.print(table)
