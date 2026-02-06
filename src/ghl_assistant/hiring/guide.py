"""Rich-rendered setup guide for manual hiring funnel resources."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

if TYPE_CHECKING:
    from ..blueprint.engine import ProvisionResult


def render_setup_guide(
    provision_result: ProvisionResult | None = None,
    pipeline_stages: list[str] | None = None,
    console: Console | None = None,
) -> None:
    """Render step-by-step guide for manual resources that couldn't be auto-provisioned.

    Args:
        provision_result: If provided, only shows steps for resources still missing.
        pipeline_stages: Pipeline stage names to include in the guide.
        console: Rich console to print to.
    """
    console = console or Console()

    # Determine what manual steps are still needed
    needs_pipeline = True
    needs_form = True
    needs_calendar = True
    needs_workflows = True

    if provision_result:
        manual_types = {a.resource_type for a in provision_result.actions if a.action == "MANUAL"}
        existing_types = {a.resource_type for a in provision_result.actions if a.action == "OK"}
        needs_pipeline = "pipelines" not in existing_types
        needs_form = "forms" not in existing_types
        needs_calendar = "calendars" not in existing_types
        needs_workflows = "workflows" not in existing_types

    if not any([needs_pipeline, needs_form, needs_calendar, needs_workflows]):
        console.print("[green]All manual resources already exist! No additional setup needed.[/green]")
        return

    console.print(Panel(
        "[bold]Manual Setup Steps[/bold]\n\n"
        "The following resources must be created in the GHL UI.\n"
        "The API does not support creating these resource types.",
        title="Hiring Funnel Setup Guide",
    ))

    step = 1

    if needs_pipeline:
        stages_text = "\n".join(
            f"      {i+1}. {s}" for i, s in enumerate(pipeline_stages or [])
        )
        console.print(f"\n[bold cyan]Step {step}: Create Pipeline[/bold cyan]")
        console.print(
            "  1. Go to [bold]Opportunities > Pipelines[/bold]\n"
            "  2. Click [bold]+ Create Pipeline[/bold]\n"
            '  3. Name it [bold]"Hiring Pipeline"[/bold]\n'
            "  4. Add these stages (in order):\n"
            f"{stages_text}\n"
            "  5. Click Save"
        )
        step += 1

    if needs_form:
        console.print(f"\n[bold cyan]Step {step}: Create Application Form[/bold cyan]")
        console.print(
            "  1. Go to [bold]Sites > Forms[/bold]\n"
            "  2. Click [bold]+ New Form[/bold]\n"
            '  3. Name it [bold]"Job Application Form"[/bold]\n'
            "  4. Add fields: First Name, Last Name, Email, Phone,\n"
            "     Position Applied, Resume URL, Desired Salary,\n"
            "     Available Start Date, Referral Source\n"
            "  5. Map custom fields to the hiring custom fields\n"
            "  6. Set form action to add tag [bold]applicant[/bold]"
        )
        step += 1

    if needs_calendar:
        console.print(f"\n[bold cyan]Step {step}: Create Interview Calendar[/bold cyan]")
        console.print(
            "  1. Go to [bold]Calendars > Calendar Settings[/bold]\n"
            "  2. Click [bold]+ Create Calendar[/bold]\n"
            '  3. Name it [bold]"Interview Calendar"[/bold]\n'
            "  4. Set availability for interview time slots\n"
            "  5. Set appointment duration (e.g. 30 or 60 minutes)\n"
            "  6. Enable confirmation/reminder notifications"
        )
        step += 1

    if needs_workflows:
        console.print(f"\n[bold cyan]Step {step}: Create Workflows (recommended)[/bold cyan]")
        _render_workflow_suggestions(console)

    console.print()


def _render_workflow_suggestions(console: Console) -> None:
    """Render suggested workflow automations."""
    table = Table(show_header=True, header_style="bold")
    table.add_column("Workflow Name", style="cyan")
    table.add_column("Trigger")
    table.add_column("Actions")

    table.add_row(
        "New Applicant",
        'Tag added: "applicant"',
        "Send confirmation email, notify hiring manager, add to Screening stage",
    )
    table.add_row(
        "Interview Scheduled",
        'Tag added: "interview-scheduled"',
        "Send interview prep email, create calendar event",
    )
    table.add_row(
        "Offer Extended",
        'Tag added: "offer-extended"',
        "Send offer email template, notify HR",
    )
    table.add_row(
        "Applicant Hired",
        'Tag added: "hired"',
        "Send welcome email, create onboarding tasks",
    )
    table.add_row(
        "Applicant Rejected",
        'Tag added: "rejected"',
        "Send rejection email after 24h delay",
    )

    console.print(f"\n  Suggested automations:")
    console.print(table)
    console.print(
        "\n  [dim]Go to Automation > Workflows to create these.[/dim]"
    )
