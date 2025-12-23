"""GHL Assistant CLI - Main entry point."""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

app = typer.Typer(
    name="ghl",
    help="GoHighLevel automation assistant - CLI tools, templates, and wizards",
    no_args_is_help=True,
)
console = Console()

# Sub-command groups
auth_app = typer.Typer(help="Authentication commands")
tdlc_app = typer.Typer(help="10DLC registration commands")
templates_app = typer.Typer(help="Workflow template commands")

app.add_typer(auth_app, name="auth")
app.add_typer(tdlc_app, name="10dlc")
app.add_typer(templates_app, name="templates")


# ============================================================================
# Auth Commands
# ============================================================================


@auth_app.command("login")
def auth_login():
    """Authenticate with GoHighLevel via OAuth."""
    console.print(
        Panel(
            "[yellow]OAuth login not yet implemented.[/yellow]\n\n"
            "For now, set your API credentials in a .env file:\n"
            "  GHL_API_KEY=your_api_key\n"
            "  GHL_LOCATION_ID=your_location_id",
            title="Authentication",
        )
    )


@auth_app.command("status")
def auth_status():
    """Check current authentication status."""
    from dotenv import dotenv_values

    config = dotenv_values(".env")

    table = Table(title="GHL Authentication Status")
    table.add_column("Setting", style="cyan")
    table.add_column("Status", style="green")

    api_key = config.get("GHL_API_KEY")
    location_id = config.get("GHL_LOCATION_ID")

    table.add_row("API Key", "Set" if api_key else "[red]Not set[/red]")
    table.add_row("Location ID", location_id if location_id else "[red]Not set[/red]")

    console.print(table)


# ============================================================================
# 10DLC Commands
# ============================================================================


@tdlc_app.command("status")
def tdlc_status():
    """Check 10DLC registration status for your account."""
    console.print(
        Panel(
            "[yellow]10DLC status check requires API integration.[/yellow]\n\n"
            "Run [bold]ghl 10dlc guide[/bold] for registration help.",
            title="10DLC Status",
        )
    )


@tdlc_app.command("guide")
def tdlc_guide():
    """Interactive guide for 10DLC registration."""
    console.print()
    console.print(
        Panel(
            "[bold cyan]10DLC Registration Guide[/bold cyan]\n\n"
            "10DLC (10-Digit Long Code) is required for business SMS in the US.\n"
            "Without proper registration, your messages may be filtered or blocked.",
            title="What is 10DLC?",
        )
    )

    console.print()
    table = Table(title="Registration Steps")
    table.add_column("Step", style="cyan", width=8)
    table.add_column("Action", style="white")
    table.add_column("Status", style="yellow", width=12)

    table.add_row("1", "Register your Brand with The Campaign Registry (TCR)", "Required")
    table.add_row("2", "Register your Campaign (what you're texting about)", "Required")
    table.add_row("3", "Wait for carrier approval (1-7 days)", "Required")
    table.add_row("4", "Link approved campaign to your GHL number", "Required")

    console.print(table)

    console.print()
    console.print(
        Panel(
            "[bold]Common Rejection Reasons:[/bold]\n\n"
            "1. Business name doesn't match EIN records exactly\n"
            "2. Website doesn't match business name\n"
            "3. Vague campaign description\n"
            "4. Missing opt-in/opt-out language\n"
            "5. Sample messages don't match campaign type\n\n"
            "[dim]Run with Claude Code for interactive assistance:[/dim]\n"
            "[bold green]/ghl-10dlc[/bold green]",
            title="Troubleshooting",
        )
    )


# ============================================================================
# Template Commands
# ============================================================================


@templates_app.command("list")
def templates_list():
    """List available workflow templates."""
    table = Table(title="Available Workflow Templates")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Category", style="yellow")
    table.add_column("Description")

    # Placeholder templates - will be loaded from templates/ directory
    templates = [
        ("lead-nurture", "Lead Nurture Sequence", "Sales", "5-touch follow-up for new leads"),
        ("appt-reminder", "Appointment Reminder", "Calendar", "SMS/email reminders before appointments"),
        ("review-request", "Review Request", "Reputation", "Ask for reviews after service"),
        ("new-lead-notify", "New Lead Notification", "Alerts", "Notify team of new leads"),
    ]

    for tid, name, cat, desc in templates:
        table.add_row(tid, name, cat, desc)

    console.print(table)
    console.print("\n[dim]Use [bold]ghl templates import <id>[/bold] to import a template[/dim]")


@templates_app.command("import")
def templates_import(template_id: str):
    """Import a workflow template to your GHL account."""
    console.print(f"[yellow]Template import not yet implemented: {template_id}[/yellow]")
    console.print("[dim]This will require API integration with your GHL account.[/dim]")


# ============================================================================
# Main
# ============================================================================


@app.command()
def version():
    """Show version information."""
    from . import __version__

    console.print(f"GHL Assistant v{__version__}")


if __name__ == "__main__":
    app()
