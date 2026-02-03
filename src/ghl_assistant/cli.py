"""GHL Assistant CLI - Main entry point."""

import asyncio
import json
from typing import Any

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
browser_app = typer.Typer(help="Browser automation and traffic capture")
contacts_app = typer.Typer(help="Contact management")
workflows_app = typer.Typer(help="Workflow management")
conversations_app = typer.Typer(help="Conversations and messaging")
calendars_app = typer.Typer(help="Calendar and appointment management")
opportunities_app = typer.Typer(help="Pipeline and opportunity management")
forms_app = typer.Typer(help="Forms and submissions")
account_app = typer.Typer(help="Account and location info")

app.add_typer(auth_app, name="auth")
app.add_typer(tdlc_app, name="10dlc")
app.add_typer(templates_app, name="templates")
app.add_typer(browser_app, name="browser")
app.add_typer(contacts_app, name="contacts")
app.add_typer(workflows_app, name="workflows")
app.add_typer(conversations_app, name="conversations")
app.add_typer(calendars_app, name="calendars")
app.add_typer(opportunities_app, name="opportunities")
app.add_typer(forms_app, name="forms")
app.add_typer(account_app, name="account")


def _output_result(result: dict[str, Any], json_output: bool = False) -> None:
    """Output result as JSON or formatted."""
    if json_output:
        console.print_json(json.dumps(result, default=str))
    else:
        # Default to JSON for complex results
        console.print_json(json.dumps(result, default=str, indent=2))


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
# Browser Commands
# ============================================================================


@browser_app.command("capture")
def browser_capture(
    url: str = typer.Option(
        "https://app.gohighlevel.com/",
        "--url", "-u",
        help="Starting URL",
    ),
    profile: str = typer.Option(
        "ghl_session",
        "--profile", "-p",
        help="Browser profile name (for cookie persistence)",
    ),
    duration: int = typer.Option(
        0,
        "--duration", "-d",
        help="Capture duration in seconds (0 = until Ctrl+C)",
    ),
    output: str = typer.Option(
        None,
        "--output", "-o",
        help="Output file path for session data",
    ),
):
    """Start a browser session and capture API traffic.

    Opens a browser window where you can interact with GHL.
    All API traffic is captured for analysis.

    First run: Log in manually (session will be saved).
    Future runs: Session is restored from cookies.
    """
    import asyncio
    from .browser.agent import run_capture_session

    console.print(
        Panel(
            f"[bold cyan]Starting Browser Capture Session[/bold cyan]\n\n"
            f"URL: {url}\n"
            f"Profile: {profile}\n"
            f"Duration: {'Until Ctrl+C' if duration == 0 else f'{duration}s'}\n\n"
            "[dim]Interact with GHL in the browser window.\n"
            "All API traffic will be captured.[/dim]",
            title="Browser Agent",
        )
    )

    try:
        result = asyncio.run(
            run_capture_session(
                url=url,
                profile=profile,
                duration=duration,
                output=output,
            )
        )

        if result.get("success"):
            console.print("\n[green]Capture session completed successfully![/green]")
        else:
            console.print(f"\n[red]Capture failed: {result.get('error')}[/red]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Capture interrupted[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")


@browser_app.command("analyze")
def browser_analyze(
    session_file: str = typer.Argument(..., help="Session JSON file to analyze"),
):
    """Analyze a captured session file.

    Shows API endpoints, auth tokens, and patterns found.
    """
    import json
    from pathlib import Path

    filepath = Path(session_file)
    if not filepath.exists():
        console.print(f"[red]File not found: {session_file}[/red]")
        raise typer.Exit(1)

    with open(filepath) as f:
        data = json.load(f)

    console.print(
        Panel(
            f"[bold]Session Analysis[/bold]\n\n"
            f"Profile: {data.get('profile', 'unknown')}\n"
            f"Captured: {data.get('captured_at', 'unknown')}\n"
            f"API calls: {len(data.get('api_calls', []))}\n"
            f"Screenshots: {len(data.get('screenshots', []))}",
            title="Session Info",
        )
    )

    # Show auth tokens
    auth = data.get("auth", {})
    if auth:
        console.print("\n[bold cyan]Auth Tokens Found:[/bold cyan]")
        table = Table()
        table.add_column("Token", style="cyan")
        table.add_column("Value (truncated)", style="white")

        for key, value in auth.items():
            display_val = str(value)[:60] + "..." if len(str(value)) > 60 else str(value)
            table.add_row(key, display_val)

        console.print(table)
    else:
        console.print("\n[yellow]No auth tokens found[/yellow]")

    # Show API endpoints
    api_calls = data.get("api_calls", [])
    if api_calls:
        console.print(f"\n[bold cyan]API Endpoints ({len(api_calls)}):[/bold cyan]")
        table = Table()
        table.add_column("Method", style="cyan", width=8)
        table.add_column("URL", style="white")
        table.add_column("Status", style="green", width=8)

        # Show first 20
        for call in api_calls[:20]:
            url = call.get("url", "")
            # Truncate URL for display
            if len(url) > 80:
                url = url[:77] + "..."
            table.add_row(
                call.get("method", "?"),
                url,
                str(call.get("response_status", "?")),
            )

        console.print(table)

        if len(api_calls) > 20:
            console.print(f"[dim]... and {len(api_calls) - 20} more[/dim]")


@browser_app.command("token")
def browser_token(
    profile: str = typer.Option(
        "ghl_session",
        "--profile", "-p",
        help="Browser profile to check",
    ),
):
    """Extract auth token from a saved browser session.

    Starts browser briefly to check current session and extract tokens.
    """
    import asyncio
    from .browser.agent import BrowserAgent

    async def extract_token():
        async with BrowserAgent(profile_name=profile, capture_network=True) as agent:
            # Navigate to GHL
            await agent.navigate("https://app.gohighlevel.com/")

            # Check if logged in
            if not await agent.is_logged_in():
                return {"success": False, "error": "Not logged in. Run 'ghl browser capture' first."}

            # Wait a moment for API calls
            await asyncio.sleep(3)

            # Extract tokens
            tokens = agent.get_auth_tokens()
            ghl_data = agent.network.get_ghl_specific() if agent.network else {}

            return {
                "success": True,
                "tokens": tokens,
                "location_id": ghl_data.get("location_id"),
            }

    console.print(f"[dim]Checking session: {profile}[/dim]")

    try:
        result = asyncio.run(extract_token())

        if result.get("success"):
            tokens = result.get("tokens", {})
            if tokens:
                console.print("\n[bold green]Auth tokens found:[/bold green]")
                for key, value in tokens.items():
                    display_val = str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
                    console.print(f"  {key}: {display_val}")

                if result.get("location_id"):
                    console.print(f"\n  location_id: {result['location_id']}")
            else:
                console.print("[yellow]No tokens captured. Try interacting with the app.[/yellow]")
        else:
            console.print(f"[red]{result.get('error')}[/red]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


# ============================================================================
# Contacts Commands
# ============================================================================


@contacts_app.command("list")
def contacts_list(
    limit: int = typer.Option(20, "--limit", "-l", help="Max contacts to return"),
    query: str = typer.Option(None, "--query", "-q", help="Search query"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """List contacts for the current location."""
    from .api import GHLClient

    async def _list():
        async with GHLClient.from_session() as ghl:
            return await ghl.contacts.list(limit=limit, query=query)

    result = asyncio.run(_list())

    if json_output:
        _output_result(result, json_output=True)
    else:
        contacts = result.get("contacts", [])
        table = Table(title=f"Contacts ({len(contacts)})")
        table.add_column("ID", style="dim", max_width=24)
        table.add_column("Name", style="cyan")
        table.add_column("Email", style="white")
        table.add_column("Phone", style="green")
        table.add_column("Tags", style="yellow")

        for c in contacts:
            name = f"{c.get('firstName', '')} {c.get('lastName', '')}".strip() or "-"
            tags = ", ".join(c.get("tags", [])[:3])
            if len(c.get("tags", [])) > 3:
                tags += "..."
            table.add_row(
                c.get("id", c.get("_id", ""))[:24],
                name,
                c.get("email", "-"),
                c.get("phone", "-"),
                tags or "-",
            )

        console.print(table)


@contacts_app.command("get")
def contacts_get(
    contact_id: str = typer.Argument(..., help="Contact ID"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Get a single contact by ID."""
    from .api import GHLClient

    async def _get():
        async with GHLClient.from_session() as ghl:
            return await ghl.contacts.get(contact_id)

    result = asyncio.run(_get())
    _output_result(result, json_output)


@contacts_app.command("create")
def contacts_create(
    first_name: str = typer.Option(None, "--first-name", "-f", help="First name"),
    last_name: str = typer.Option(None, "--last-name", "-l", help="Last name"),
    email: str = typer.Option(None, "--email", "-e", help="Email address"),
    phone: str = typer.Option(None, "--phone", "-p", help="Phone number (E.164)"),
    tags: str = typer.Option(None, "--tags", "-t", help="Comma-separated tags"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Create a new contact."""
    from .api import GHLClient

    tag_list = [t.strip() for t in tags.split(",")] if tags else None

    async def _create():
        async with GHLClient.from_session() as ghl:
            return await ghl.contacts.create(
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone,
                tags=tag_list,
            )

    result = asyncio.run(_create())
    _output_result(result, json_output)
    console.print("[green]Contact created successfully![/green]")


@contacts_app.command("search")
def contacts_search(
    query: str = typer.Argument(..., help="Search query (name, email, phone)"),
    limit: int = typer.Option(20, "--limit", "-l", help="Max results"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Search contacts by name, email, or phone."""
    from .api import GHLClient

    async def _search():
        async with GHLClient.from_session() as ghl:
            return await ghl.contacts.search(query=query, limit=limit)

    result = asyncio.run(_search())

    if json_output:
        _output_result(result, json_output=True)
    else:
        contacts = result.get("contacts", [])
        console.print(f"[dim]Found {len(contacts)} contacts matching '{query}'[/dim]\n")
        for c in contacts:
            name = f"{c.get('firstName', '')} {c.get('lastName', '')}".strip() or "No name"
            console.print(f"  [cyan]{name}[/cyan] ({c.get('email', 'no email')})")


# ============================================================================
# Workflows Commands
# ============================================================================


@workflows_app.command("list")
def workflows_list(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """List all workflows for the current location."""
    from .api import GHLClient

    async def _list():
        async with GHLClient.from_session() as ghl:
            return await ghl.workflows.list()

    result = asyncio.run(_list())

    if json_output:
        _output_result(result, json_output=True)
    else:
        workflows = result.get("workflows", [])
        table = Table(title=f"Workflows ({len(workflows)})")
        table.add_column("ID", style="dim", max_width=24)
        table.add_column("Name", style="cyan")
        table.add_column("Status", style="green")

        for w in workflows:
            status = w.get("status", "unknown")
            status_style = "green" if status == "published" else "yellow"
            table.add_row(
                w.get("id", w.get("_id", ""))[:24],
                w.get("name", "-"),
                f"[{status_style}]{status}[/{status_style}]",
            )

        console.print(table)


@workflows_app.command("add-contact")
def workflows_add_contact(
    workflow_id: str = typer.Argument(..., help="Workflow ID"),
    contact_id: str = typer.Argument(..., help="Contact ID"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Add a contact to a workflow."""
    from .api import GHLClient

    async def _add():
        async with GHLClient.from_session() as ghl:
            return await ghl.workflows.add_contact(workflow_id, contact_id)

    result = asyncio.run(_add())
    _output_result(result, json_output)
    console.print("[green]Contact added to workflow![/green]")


# ============================================================================
# Conversations Commands
# ============================================================================


@conversations_app.command("list")
def conversations_list(
    limit: int = typer.Option(20, "--limit", "-l", help="Max conversations"),
    unread: bool = typer.Option(False, "--unread", "-u", help="Only unread"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """List conversations for the current location."""
    from .api import GHLClient

    async def _list():
        async with GHLClient.from_session() as ghl:
            return await ghl.conversations.list(limit=limit, unread_only=unread)

    result = asyncio.run(_list())

    if json_output:
        _output_result(result, json_output=True)
    else:
        conversations = result.get("conversations", [])
        table = Table(title=f"Conversations ({len(conversations)})")
        table.add_column("ID", style="dim", max_width=24)
        table.add_column("Contact", style="cyan")
        table.add_column("Type", style="yellow")
        table.add_column("Unread", style="red")

        for c in conversations:
            table.add_row(
                c.get("id", c.get("_id", ""))[:24],
                c.get("contactName", c.get("contactId", "-")),
                c.get("type", "-"),
                str(c.get("unreadCount", 0)),
            )

        console.print(table)


@conversations_app.command("send-sms")
def conversations_send_sms(
    contact_id: str = typer.Argument(..., help="Contact ID"),
    message: str = typer.Argument(..., help="SMS message text"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Send an SMS message to a contact."""
    from .api import GHLClient

    async def _send():
        async with GHLClient.from_session() as ghl:
            return await ghl.conversations.send_sms(contact_id, message)

    result = asyncio.run(_send())
    _output_result(result, json_output)
    console.print("[green]SMS sent![/green]")


@conversations_app.command("send-email")
def conversations_send_email(
    contact_id: str = typer.Argument(..., help="Contact ID"),
    subject: str = typer.Argument(..., help="Email subject"),
    body: str = typer.Argument(..., help="Email body (HTML supported)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Send an email to a contact."""
    from .api import GHLClient

    async def _send():
        async with GHLClient.from_session() as ghl:
            return await ghl.conversations.send_email(contact_id, subject, body)

    result = asyncio.run(_send())
    _output_result(result, json_output)
    console.print("[green]Email sent![/green]")


# ============================================================================
# Calendars Commands
# ============================================================================


@calendars_app.command("list")
def calendars_list(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """List all calendars for the current location."""
    from .api import GHLClient

    async def _list():
        async with GHLClient.from_session() as ghl:
            return await ghl.calendars.list()

    result = asyncio.run(_list())

    if json_output:
        _output_result(result, json_output=True)
    else:
        calendars = result.get("calendars", [])
        table = Table(title=f"Calendars ({len(calendars)})")
        table.add_column("ID", style="dim", max_width=24)
        table.add_column("Name", style="cyan")
        table.add_column("Event Type", style="yellow")

        for c in calendars:
            table.add_row(
                c.get("id", c.get("_id", ""))[:24],
                c.get("name", "-"),
                c.get("eventType", "-"),
            )

        console.print(table)


@calendars_app.command("slots")
def calendars_slots(
    calendar_id: str = typer.Argument(..., help="Calendar ID"),
    date: str = typer.Argument(..., help="Date (YYYY-MM-DD)"),
    end_date: str = typer.Option(None, "--end", "-e", help="End date"),
    timezone: str = typer.Option("America/New_York", "--tz", help="Timezone"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Get available slots for a calendar."""
    from .api import GHLClient

    async def _slots():
        async with GHLClient.from_session() as ghl:
            return await ghl.calendars.get_slots(
                calendar_id, date, end_date=end_date, timezone=timezone
            )

    result = asyncio.run(_slots())
    _output_result(result, json_output)


@calendars_app.command("book")
def calendars_book(
    calendar_id: str = typer.Argument(..., help="Calendar ID"),
    contact_id: str = typer.Argument(..., help="Contact ID"),
    slot_time: str = typer.Argument(..., help="Slot time (ISO format)"),
    title: str = typer.Option(None, "--title", "-t", help="Appointment title"),
    notes: str = typer.Option(None, "--notes", "-n", help="Appointment notes"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Book an appointment."""
    from .api import GHLClient

    async def _book():
        async with GHLClient.from_session() as ghl:
            return await ghl.calendars.book(
                calendar_id, contact_id, slot_time, title=title, notes=notes
            )

    result = asyncio.run(_book())
    _output_result(result, json_output)
    console.print("[green]Appointment booked![/green]")


# ============================================================================
# Opportunities Commands
# ============================================================================


@opportunities_app.command("pipelines")
def opportunities_pipelines(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """List all pipelines for the current location."""
    from .api import GHLClient

    async def _list():
        async with GHLClient.from_session() as ghl:
            return await ghl.opportunities.pipelines()

    result = asyncio.run(_list())

    if json_output:
        _output_result(result, json_output=True)
    else:
        pipelines = result.get("pipelines", [])
        table = Table(title=f"Pipelines ({len(pipelines)})")
        table.add_column("ID", style="dim", max_width=24)
        table.add_column("Name", style="cyan")
        table.add_column("Stages", style="yellow")

        for p in pipelines:
            stages = [s.get("name", "") for s in p.get("stages", [])]
            table.add_row(
                p.get("id", p.get("_id", ""))[:24],
                p.get("name", "-"),
                " → ".join(stages[:4]) + ("..." if len(stages) > 4 else ""),
            )

        console.print(table)


@opportunities_app.command("list")
def opportunities_list(
    pipeline_id: str = typer.Option(None, "--pipeline", "-p", help="Filter by pipeline"),
    limit: int = typer.Option(20, "--limit", "-l", help="Max results"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """List opportunities."""
    from .api import GHLClient

    async def _list():
        async with GHLClient.from_session() as ghl:
            return await ghl.opportunities.list(pipeline_id=pipeline_id, limit=limit)

    result = asyncio.run(_list())

    if json_output:
        _output_result(result, json_output=True)
    else:
        opps = result.get("opportunities", [])
        table = Table(title=f"Opportunities ({len(opps)})")
        table.add_column("ID", style="dim", max_width=24)
        table.add_column("Name", style="cyan")
        table.add_column("Value", style="green")
        table.add_column("Status", style="yellow")

        for o in opps:
            value = o.get("monetaryValue")
            value_str = f"${value:,.2f}" if value else "-"
            table.add_row(
                o.get("id", o.get("_id", ""))[:24],
                o.get("name", "-"),
                value_str,
                o.get("status", "-"),
            )

        console.print(table)


@opportunities_app.command("create")
def opportunities_create(
    pipeline_id: str = typer.Argument(..., help="Pipeline ID"),
    stage_id: str = typer.Argument(..., help="Initial stage ID"),
    contact_id: str = typer.Argument(..., help="Contact ID"),
    name: str = typer.Argument(..., help="Opportunity name"),
    value: float = typer.Option(None, "--value", "-v", help="Monetary value"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Create a new opportunity."""
    from .api import GHLClient

    async def _create():
        async with GHLClient.from_session() as ghl:
            return await ghl.opportunities.create(
                pipeline_id=pipeline_id,
                stage_id=stage_id,
                contact_id=contact_id,
                name=name,
                value=value,
            )

    result = asyncio.run(_create())
    _output_result(result, json_output)
    console.print("[green]Opportunity created![/green]")


@opportunities_app.command("move")
def opportunities_move(
    opportunity_id: str = typer.Argument(..., help="Opportunity ID"),
    stage_id: str = typer.Argument(..., help="Target stage ID"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Move an opportunity to a new stage."""
    from .api import GHLClient

    async def _move():
        async with GHLClient.from_session() as ghl:
            return await ghl.opportunities.move_stage(opportunity_id, stage_id)

    result = asyncio.run(_move())
    _output_result(result, json_output)
    console.print("[green]Opportunity moved![/green]")


# ============================================================================
# Forms Commands
# ============================================================================


@forms_app.command("list")
def forms_list(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """List all forms for the current location."""
    from .api import GHLClient

    async def _list():
        async with GHLClient.from_session() as ghl:
            return await ghl.forms.list()

    result = asyncio.run(_list())

    if json_output:
        _output_result(result, json_output=True)
    else:
        forms = result.get("forms", [])
        table = Table(title=f"Forms ({len(forms)})")
        table.add_column("ID", style="dim", max_width=24)
        table.add_column("Name", style="cyan")

        for f in forms:
            table.add_row(
                f.get("id", f.get("_id", ""))[:24],
                f.get("name", "-"),
            )

        console.print(table)


@forms_app.command("submissions")
def forms_submissions(
    form_id: str = typer.Argument(..., help="Form ID"),
    limit: int = typer.Option(50, "--limit", "-l", help="Max submissions"),
    page: int = typer.Option(1, "--page", "-p", help="Page number"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Get form submissions."""
    from .api import GHLClient

    async def _subs():
        async with GHLClient.from_session() as ghl:
            return await ghl.forms.submissions(form_id, limit=limit, page=page)

    result = asyncio.run(_subs())
    _output_result(result, json_output)


# ============================================================================
# Account Commands
# ============================================================================


@account_app.command("info")
def account_info(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Show current account and session info."""
    from .api import GHLClient

    async def _info():
        async with GHLClient.from_session() as ghl:
            info = {
                "config": ghl.config.to_dict(),
            }
            if ghl.config.user_id:
                try:
                    info["user"] = await ghl.get_user()
                except Exception:
                    pass
            if ghl.config.company_id:
                try:
                    info["company"] = await ghl.get_company()
                except Exception:
                    pass
            return info

    result = asyncio.run(_info())

    if json_output:
        _output_result(result, json_output=True)
    else:
        config = result.get("config", {})
        console.print(
            Panel(
                f"[bold]Session Info[/bold]\n\n"
                f"User ID: {config.get('user_id', 'N/A')}\n"
                f"Company ID: {config.get('company_id', 'N/A')}\n"
                f"Location ID: {config.get('location_id', 'N/A')}\n"
                f"Token: {config.get('token', 'N/A')}",
                title="GHL Account",
            )
        )

        user = result.get("user", {})
        if user:
            console.print(
                f"\n[cyan]User:[/cyan] {user.get('firstName', '')} {user.get('lastName', '')} "
                f"({user.get('email', '')})"
            )

        company = result.get("company", {})
        if company:
            console.print(f"[cyan]Company:[/cyan] {company.get('name', 'N/A')}")


@account_app.command("locations")
def account_locations(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """List locations for the current company."""
    from .api import GHLClient

    async def _locations():
        async with GHLClient.from_session() as ghl:
            return await ghl.search_locations()

    result = asyncio.run(_locations())

    if json_output:
        _output_result(result, json_output=True)
    else:
        locations = result.get("locations", [])
        table = Table(title=f"Locations ({len(locations)})")
        table.add_column("ID", style="dim", max_width=24)
        table.add_column("Name", style="cyan")
        table.add_column("Phone", style="green")
        table.add_column("Email", style="white")

        for loc in locations:
            table.add_row(
                loc.get("_id", loc.get("id", ""))[:24],
                loc.get("name", "-"),
                loc.get("phone", "-"),
                loc.get("email", "-"),
            )

        console.print(table)


# ============================================================================
# Blueprint Commands (snapshot / provision / audit / bulk)
# ============================================================================

bulk_app = typer.Typer(help="Cross-location bulk operations")
app.add_typer(bulk_app, name="bulk")


@app.command()
def snapshot(
    output: str = typer.Option("blueprint.yaml", "--output", "-o", help="Output YAML file path"),
    name: str = typer.Option("Location Blueprint", "--name", "-n", help="Blueprint name"),
    location_id: str = typer.Option(None, "--location", "-l", help="Location ID (default: session)"),
):
    """Snapshot a location's config to a YAML blueprint."""
    from .api import GHLClient
    from .blueprint.serialization import save_blueprint

    async def _snapshot():
        async with GHLClient.from_session() as ghl:
            from .blueprint.engine import snapshot_location
            result = await snapshot_location(ghl, name=name, location_id=location_id)
            return result

    with console.status("[bold cyan]Snapshotting location...[/bold cyan]"):
        result = asyncio.run(_snapshot())

    # Show warnings for failed API calls
    if result.warnings:
        for warn in result.warnings:
            console.print(f"[yellow]Warning: {warn}[/yellow]")

    filepath = save_blueprint(result.blueprint, output)
    bp = result.blueprint

    # Summary
    sections = bp.resource_sections()
    total = sum(len(v) for v in sections.values())

    console.print(
        Panel(
            f"[bold green]Blueprint saved![/bold green]\n\n"
            f"File: {filepath}\n"
            f"Name: {bp.metadata.name}\n"
            f"Source: {bp.metadata.source_location_id}\n"
            f"Resources: {total} total\n\n"
            + "\n".join(
                f"  {k}: {len(v)}" for k, v in sections.items() if v
            ),
            title="Snapshot Complete",
        )
    )


@app.command()
def provision(
    blueprint_file: str = typer.Argument(..., help="Path to blueprint YAML file"),
    location_id: str = typer.Option(None, "--location", "-l", help="Target location ID"),
    dry_run: bool = typer.Option(True, "--dry-run/--apply", help="Dry-run (default) or apply changes"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Apply a blueprint to a location. Dry-run by default."""
    from .api import GHLClient
    from .blueprint.serialization import load_blueprint
    from .blueprint.diff import render_plan

    bp = load_blueprint(blueprint_file)

    # Always compute plan first (dry-run)
    async def _plan():
        async with GHLClient.from_session() as ghl:
            from .blueprint.engine import provision_location
            return await provision_location(ghl, bp, location_id=location_id, dry_run=True)

    with console.status("[bold cyan]Computing plan...[/bold cyan]"):
        plan = asyncio.run(_plan())

    render_plan(plan, console)

    if dry_run:
        console.print("[dim]This is a dry run. Use --apply to execute changes.[/dim]")
        return

    # Apply mode: confirm before executing
    changes = plan.created + plan.updated
    if changes == 0:
        console.print("[green]Nothing to apply. Location matches blueprint.[/green]")
        return

    if not yes:
        confirm = typer.confirm(
            f"Apply {changes} change(s) to the location?",
            default=False,
        )
        if not confirm:
            console.print("[yellow]Aborted.[/yellow]")
            raise typer.Exit(0)

    async def _apply():
        async with GHLClient.from_session() as ghl:
            from .blueprint.engine import provision_location
            return await provision_location(ghl, bp, location_id=location_id, dry_run=False)

    with console.status("[bold cyan]Applying changes...[/bold cyan]"):
        result = asyncio.run(_apply())

    if result.errors:
        console.print(f"\n[red]{len(result.errors)} errors occurred:[/red]")
        for err in result.errors:
            console.print(f"  [red]- {err}[/red]")
    else:
        console.print("[green]Provision completed successfully![/green]")


@app.command()
def audit(
    blueprint_file: str = typer.Argument(..., help="Path to blueprint YAML file"),
    location_id: str = typer.Option(None, "--location", "-l", help="Location ID to audit"),
    health: bool = typer.Option(True, "--health/--no-health", help="Run health checks"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Audit a location against a blueprint + run health checks."""
    from .api import GHLClient
    from .blueprint.serialization import load_blueprint

    bp = load_blueprint(blueprint_file)

    async def _audit():
        async with GHLClient.from_session() as ghl:
            from .blueprint.engine import audit_location
            return await audit_location(ghl, bp, location_id=location_id, run_health=health)

    with console.status("[bold cyan]Auditing location...[/bold cyan]"):
        result = asyncio.run(_audit())

    if json_output:
        audit_data = {
            "compliance_score": result.compliance_score,
            "total_resources": result.total_resources,
            "matched_resources": result.matched_resources,
            "actions": [
                {
                    "resource_type": a.resource_type,
                    "name": a.name,
                    "action": a.action,
                    "details": a.details,
                }
                for a in result.plan.actions
            ],
            "health": result.health,
        }
        _output_result(audit_data, json_output=True)
    else:
        from .blueprint.diff import render_audit
        render_audit(
            result.plan,
            health=result.health,
            compliance_score=result.compliance_score,
            console=console,
        )


@bulk_app.command("snapshot")
def bulk_snapshot_cmd(
    output_dir: str = typer.Option("./blueprints", "-o", help="Output directory for YAML files"),
):
    """Snapshot all locations in the company to YAML blueprints."""
    from .api import GHLClient

    async def _bulk_snapshot():
        async with GHLClient.from_session() as ghl:
            from .blueprint.engine import bulk_snapshot
            return await bulk_snapshot(ghl, output_dir=output_dir)

    with console.status("[bold cyan]Snapshotting all locations...[/bold cyan]"):
        results = asyncio.run(_bulk_snapshot())

    table = Table(title=f"Bulk Snapshot ({len(results)} locations)")
    table.add_column("Location", style="cyan")
    table.add_column("File", style="white")

    for loc_name, filepath in results:
        table.add_row(loc_name, filepath)

    console.print(table)
    console.print(f"\n[green]Saved {len(results)} blueprints to {output_dir}/[/green]")


@bulk_app.command("audit")
def bulk_audit_cmd(
    blueprint_file: str = typer.Argument(..., help="Path to blueprint YAML file"),
):
    """Audit all locations against a blueprint."""
    from .api import GHLClient
    from .blueprint.serialization import load_blueprint

    bp = load_blueprint(blueprint_file)

    async def _bulk_audit():
        async with GHLClient.from_session() as ghl:
            from .blueprint.engine import bulk_audit
            return await bulk_audit(ghl, bp)

    with console.status("[bold cyan]Auditing all locations...[/bold cyan]"):
        results = asyncio.run(_bulk_audit())

    from .blueprint.diff import render_bulk_audit
    render_bulk_audit(results, console)


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
