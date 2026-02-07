"""MaxLevel CLI - Main entry point."""

import asyncio
import json
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

app = typer.Typer(
    name="maxlevel",
    help="MaxLevel — GoHighLevel automation platform",
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
ai_app = typer.Typer(help="Conversation AI agent management")
voice_app = typer.Typer(help="Voice AI agent management")
agency_app = typer.Typer(help="Agency-level sub-account management")
hiring_app = typer.Typer(help="Hiring funnel setup and applicant management")
crm_app = typer.Typer(help="CRM platform management")
dashboard_app = typer.Typer(help="Unified dashboard management")

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
app.add_typer(ai_app, name="ai")
app.add_typer(voice_app, name="voice")
app.add_typer(agency_app, name="agency")
app.add_typer(hiring_app, name="hiring")
app.add_typer(crm_app, name="crm")
app.add_typer(dashboard_app, name="dashboard")


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

oauth_app = typer.Typer(help="OAuth authentication commands")
app.add_typer(oauth_app, name="oauth")


@auth_app.command("quick")
def auth_quick(
    profile: str = typer.Option(
        "ghl_session",
        "--profile", "-p",
        help="Browser profile name",
    ),
    timeout: int = typer.Option(
        300,
        "--timeout", "-t",
        help="Max seconds to wait for login",
    ),
):
    """Quick one-command token capture from browser.

    Opens a browser, waits for you to log in (if needed),
    captures the session token, and stores it for API use.
    """
    from .browser.agent import BrowserAgent
    from .auth import TokenManager

    async def _quick_capture():
        async with BrowserAgent(profile_name=profile, capture_network=True) as agent:
            # Navigate to GHL
            console.print("[dim]Opening browser...[/dim]")
            await agent.navigate("https://app.gohighlevel.com/")

            # Check if logged in
            if not await agent.is_logged_in():
                console.print(
                    Panel(
                        "[bold yellow]Please log in to GoHighLevel in the browser window.[/bold yellow]\n\n"
                        "Your session will be saved for future API access.",
                        title="Login Required",
                    )
                )

                # Wait for login
                import time
                start = time.time()
                while time.time() - start < timeout:
                    await asyncio.sleep(2)
                    if await agent.is_logged_in():
                        console.print("[green]Login detected![/green]")
                        break
                else:
                    return {"success": False, "error": "Login timeout"}

            # Try Vue store extraction first (fastest method)
            console.print("[dim]Extracting token from Vue store...[/dim]")
            vue_data = await agent.extract_vue_token()
            if vue_data and vue_data.get("authToken"):
                manager = TokenManager()
                manager.save_session_from_capture(
                    token=vue_data["authToken"],
                    company_id=vue_data.get("companyId"),
                    user_id=vue_data.get("userId"),
                )
                return {
                    "success": True,
                    "company_id": vue_data.get("companyId"),
                    "method": "vue_store",
                }

            # Fall back to network capture
            console.print("[dim]Vue store extraction failed, trying network capture...[/dim]")
            await asyncio.sleep(3)

            tokens = agent.get_auth_tokens()
            ghl_data = agent.network.get_ghl_specific() if agent.network else {}

            if not tokens.get("access_token"):
                # Navigate to a data-heavy page to trigger API calls
                await agent.navigate("https://app.gohighlevel.com/contacts/")
                await asyncio.sleep(3)
                tokens = agent.get_auth_tokens()
                ghl_data = agent.network.get_ghl_specific() if agent.network else {}

            if not tokens.get("access_token"):
                return {"success": False, "error": "Could not capture auth token"}

            # Save to token manager
            manager = TokenManager()
            manager.save_session_from_capture(
                token=tokens["access_token"],
                location_id=ghl_data.get("location_id"),
                company_id=ghl_data.get("auth", {}).get("companyId"),
                user_id=ghl_data.get("auth", {}).get("userId"),
            )

            return {
                "success": True,
                "location_id": ghl_data.get("location_id"),
                "company_id": ghl_data.get("auth", {}).get("companyId"),
                "method": "network_capture",
            }

    try:
        result = asyncio.run(_quick_capture())

        if result.get("success"):
            console.print(
                Panel(
                    f"[bold green]Session captured successfully![/bold green]\n\n"
                    f"Location ID: {result.get('location_id', 'N/A')}\n"
                    f"Company ID: {result.get('company_id', 'N/A')}\n\n"
                    "[dim]You can now use 'maxlevel contacts list' and other API commands.[/dim]",
                    title="Auth Complete",
                )
            )
        else:
            console.print(f"[red]Error: {result.get('error')}[/red]")
            raise typer.Exit(1)

    except KeyboardInterrupt:
        console.print("\n[yellow]Capture cancelled[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@auth_app.command("status")
def auth_status():
    """Check current authentication status and token health."""
    from .auth import TokenManager

    manager = TokenManager()
    status = manager.get_status()

    console.print(Panel("[bold]GHL Authentication Status[/bold]", expand=False))

    # OAuth status
    oauth_info = status.get("oauth_token")
    if oauth_info:
        if oauth_info["valid"]:
            expires_in = oauth_info["expires_in_seconds"]
            if expires_in > 3600:
                expiry_str = f"[green]{expires_in // 3600}h {(expires_in % 3600) // 60}m[/green]"
            elif expires_in > 300:
                expiry_str = f"[yellow]{expires_in // 60}m[/yellow]"
            else:
                expiry_str = f"[red]{expires_in}s (refresh soon)[/red]"

            console.print(f"\n[bold cyan]OAuth Token[/bold cyan]")
            console.print(f"  Status: [green]Valid[/green]")
            console.print(f"  Expires in: {expiry_str}")
            console.print(f"  Company ID: {oauth_info.get('company_id', 'N/A')}")
            console.print(f"  Location ID: {oauth_info.get('location_id', 'N/A')}")
            console.print(f"  Scope: {oauth_info.get('scope', 'N/A')}")
        else:
            console.print(f"\n[bold cyan]OAuth Token[/bold cyan]")
            console.print(f"  Status: [red]Expired[/red] (will auto-refresh)")
    elif status.get("oauth_configured"):
        console.print(f"\n[bold cyan]OAuth[/bold cyan]")
        console.print(f"  Status: [yellow]Configured but no token[/yellow]")
        console.print(f"  [dim]Run 'maxlevel oauth connect' to authenticate[/dim]")
    else:
        console.print(f"\n[bold cyan]OAuth[/bold cyan]")
        console.print(f"  Status: [dim]Not configured[/dim]")
        console.print(f"  [dim]Run 'maxlevel oauth setup' to configure[/dim]")

    # Session token status
    session_info = status.get("session_token")
    if session_info:
        age = session_info["age_hours"]
        if age < 12:
            age_str = f"[green]{age:.1f}h ago[/green]"
        elif age < 24:
            age_str = f"[yellow]{age:.1f}h ago[/yellow]"
        else:
            age_str = f"[red]{age:.1f}h ago (may be expired)[/red]"

        console.print(f"\n[bold cyan]Session Token[/bold cyan]")
        console.print(f"  Status: [green]Available[/green]")
        console.print(f"  Captured: {age_str}")
        console.print(f"  Company ID: {session_info.get('company_id', 'N/A')}")
        console.print(f"  Location ID: {session_info.get('location_id', 'N/A')}")
        console.print(f"  User ID: {session_info.get('user_id', 'N/A')}")
    else:
        console.print(f"\n[bold cyan]Session Token[/bold cyan]")
        console.print(f"  Status: [dim]Not available[/dim]")
        console.print(f"  [dim]Run 'maxlevel auth quick' to capture[/dim]")

    # Summary
    has_auth = oauth_info or session_info
    if has_auth:
        console.print(f"\n[green]API access: Ready[/green]")
    else:
        console.print(f"\n[red]API access: Not authenticated[/red]")
        console.print("[dim]Run 'maxlevel oauth connect' (recommended) or 'maxlevel auth quick'[/dim]")


@auth_app.command("clear")
def auth_clear(
    oauth_only: bool = typer.Option(False, "--oauth", help="Clear only OAuth tokens"),
    session_only: bool = typer.Option(False, "--session", help="Clear only session tokens"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Clear stored authentication tokens."""
    from .auth import TokenManager

    if not force:
        if oauth_only:
            msg = "Clear OAuth tokens?"
        elif session_only:
            msg = "Clear session token?"
        else:
            msg = "Clear all authentication tokens?"

        if not typer.confirm(msg):
            console.print("[yellow]Cancelled[/yellow]")
            raise typer.Exit(0)

    manager = TokenManager()

    if oauth_only:
        manager.storage.clear_oauth()
        console.print("[green]OAuth tokens cleared[/green]")
    elif session_only:
        manager.storage.clear_session()
        console.print("[green]Session token cleared[/green]")
    else:
        manager.clear_all()
        console.print("[green]All tokens cleared[/green]")


@auth_app.command("bridge")
def auth_bridge(
    port: int = typer.Option(3456, "--port", "-p", help="Bridge server port"),
    timeout: int = typer.Option(120, "--timeout", "-t", help="Max seconds to wait for token"),
):
    """Capture GHL token via bookmarklet from an existing browser session.

    Starts a local server with a bookmarklet page. Drag the bookmarklet
    to your bookmarks bar, then click it on any GHL page to capture
    the session token.

    This method works with your existing Chrome session - no need to
    open a new browser window.
    """
    import webbrowser
    from .auth import TokenManager, TokenBridgeServer

    server = TokenBridgeServer(port=port)

    try:
        actual_port = server.start()
        url = f"http://localhost:{actual_port}/"

        console.print(
            Panel(
                "[bold]GHL Token Bridge[/bold]\n\n"
                "A browser tab will open with a bookmarklet button.\n\n"
                "1. Drag the button to your bookmarks bar\n"
                "2. Navigate to app.gohighlevel.com (log in if needed)\n"
                "3. Click the bookmarklet\n\n"
                f"Bridge server running on: {url}",
                title="Token Bridge",
            )
        )

        webbrowser.open(url)
        console.print("[dim]Waiting for token...[/dim]")

        token_data = server.wait_for_token(timeout=timeout)

        # Save token
        manager = TokenManager()
        manager.save_session_from_capture(
            token=token_data["authToken"],
            company_id=token_data.get("companyId"),
            user_id=token_data.get("userId"),
        )

        console.print(
            Panel(
                f"[bold green]Token captured successfully![/bold green]\n\n"
                f"Company ID: {token_data.get('companyId', 'N/A')}\n"
                f"User ID: {token_data.get('userId', 'N/A')}\n\n"
                "[dim]You can now use 'maxlevel contacts list' and other API commands.[/dim]",
                title="Auth Complete",
            )
        )

    except TimeoutError:
        console.print("[red]Timeout waiting for token. Make sure you clicked the bookmarklet on a GHL page.[/red]")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Bridge cancelled[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    finally:
        server.stop()


# OAuth sub-commands

@oauth_app.command("setup")
def oauth_setup(
    client_id: str = typer.Option(None, "--client-id", "-c", help="OAuth Client ID"),
    client_secret: str = typer.Option(None, "--client-secret", "-s", help="OAuth Client Secret"),
    redirect_uri: str = typer.Option(
        "http://localhost:3000/callback",
        "--redirect-uri", "-r",
        help="OAuth redirect URI",
    ),
    scopes: str = typer.Option(
        None,
        "--scopes",
        help="Comma-separated scopes (e.g., contacts.readonly,contacts.write)",
    ),
):
    """Configure OAuth client credentials for GHL Marketplace App.

    You can get client credentials by creating a Private App in the
    GHL Marketplace: https://marketplace.gohighlevel.com/

    If not provided via options, you'll be prompted to enter them.
    """
    from .oauth import TokenStorage, OAuthConfig

    # Interactive prompts if not provided
    if not client_id:
        console.print(
            Panel(
                "[bold]GHL Marketplace OAuth Setup[/bold]\n\n"
                "You'll need a Private App from the GHL Marketplace.\n"
                "Go to: https://marketplace.gohighlevel.com/\n\n"
                "1. Click 'My Apps' → 'Create App'\n"
                "2. Choose 'Private' distribution\n"
                "3. Configure scopes for your use case\n"
                "4. Copy the Client ID and Client Secret",
                title="OAuth Setup",
            )
        )
        client_id = typer.prompt("Client ID")

    if not client_secret:
        client_secret = typer.prompt("Client Secret", hide_input=True)

    scope_list = [s.strip() for s in scopes.split(",")] if scopes else []

    # Save config
    storage = TokenStorage()
    config = OAuthConfig(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scopes=scope_list,
    )
    storage.save_oauth_config(config)

    console.print(
        Panel(
            f"[green]OAuth configuration saved![/green]\n\n"
            f"Client ID: {client_id[:8]}...{client_id[-4:]}\n"
            f"Redirect URI: {redirect_uri}\n"
            f"Scopes: {', '.join(scope_list) if scope_list else 'All available'}\n\n"
            "[dim]Run 'maxlevel oauth connect' to complete authentication[/dim]",
            title="Setup Complete",
        )
    )


@oauth_app.command("connect")
def oauth_connect(
    port: int = typer.Option(3000, "--port", "-p", help="Local server port for callback"),
    timeout: int = typer.Option(300, "--timeout", "-t", help="Max seconds to wait"),
):
    """Start OAuth flow to connect your GHL account.

    Opens a browser window where you'll authorize the app.
    After authorization, tokens are stored for API access.
    """
    from .oauth import OAuthClient, TokenStorage, run_oauth_flow, OAuthError

    storage = TokenStorage()

    if not storage.has_oauth_config():
        console.print("[red]OAuth not configured. Run 'maxlevel oauth setup' first.[/red]")
        raise typer.Exit(1)

    try:
        client = OAuthClient.from_config(storage)

        console.print(
            Panel(
                "[bold]Starting OAuth Authorization[/bold]\n\n"
                "A browser window will open for you to authorize the app.\n"
                "After authorization, you'll be redirected back.\n\n"
                f"Listening on: http://localhost:{port}/callback",
                title="OAuth Connect",
            )
        )

        tokens = asyncio.run(run_oauth_flow(
            client=client,
            storage=storage,
            port=port,
            timeout=timeout,
        ))

        console.print(
            Panel(
                f"[bold green]Authorization successful![/bold green]\n\n"
                f"Access Token: Valid for 24 hours\n"
                f"Refresh Token: Valid for 1 year\n"
                f"Company ID: {tokens.company_id or 'N/A'}\n"
                f"Location ID: {tokens.location_id or 'N/A'}\n\n"
                "[dim]Tokens will auto-refresh when needed.[/dim]",
                title="Connected",
            )
        )

    except OAuthError as e:
        console.print(f"[red]OAuth error: {e}[/red]")
        if e.details:
            console.print(f"[dim]Details: {e.details}[/dim]")
        raise typer.Exit(1)
    except TimeoutError:
        console.print("[red]Authorization timed out. Please try again.[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@oauth_app.command("status")
def oauth_status():
    """Show OAuth token status."""
    from .oauth import TokenStorage

    storage = TokenStorage()
    status = storage.get_status()

    if not status.get("oauth_configured"):
        console.print("[yellow]OAuth not configured. Run 'maxlevel oauth setup' first.[/yellow]")
        return

    oauth_info = status.get("oauth_token")
    if not oauth_info:
        console.print("[yellow]No OAuth token. Run 'maxlevel oauth connect' to authenticate.[/yellow]")
        return

    if oauth_info["valid"]:
        expires_in = oauth_info["expires_in_seconds"]
        hours = expires_in // 3600
        minutes = (expires_in % 3600) // 60

        console.print(
            Panel(
                f"[bold green]OAuth Token Valid[/bold green]\n\n"
                f"Expires in: {hours}h {minutes}m\n"
                f"Company ID: {oauth_info.get('company_id', 'N/A')}\n"
                f"Location ID: {oauth_info.get('location_id', 'N/A')}\n"
                f"Scope: {oauth_info.get('scope', 'N/A')}",
                title="OAuth Status",
            )
        )
    else:
        console.print(
            Panel(
                "[bold yellow]OAuth Token Expired[/bold yellow]\n\n"
                "The token will be automatically refreshed on next API call.\n"
                "Or run 'maxlevel oauth refresh' to refresh now.",
                title="OAuth Status",
            )
        )


@oauth_app.command("refresh")
def oauth_refresh():
    """Force refresh OAuth access token."""
    from .oauth import OAuthClient, TokenStorage, OAuthError

    storage = TokenStorage()
    data = storage.load()

    if not data.oauth:
        console.print("[red]No OAuth token to refresh. Run 'maxlevel oauth connect' first.[/red]")
        raise typer.Exit(1)

    try:
        client = OAuthClient.from_config(storage)

        console.print("[dim]Refreshing token...[/dim]")
        tokens = asyncio.run(client.refresh_tokens(data.oauth.refresh_token))

        storage.save_oauth_tokens(tokens.to_storage_data())

        expires_in = tokens.expires_in
        hours = expires_in // 3600
        minutes = (expires_in % 3600) // 60

        console.print(f"[green]Token refreshed! Valid for {hours}h {minutes}m[/green]")

    except OAuthError as e:
        console.print(f"[red]Refresh failed: {e}[/red]")
        console.print("[dim]You may need to run 'maxlevel oauth connect' again.[/dim]")
        raise typer.Exit(1)


@oauth_app.command("revoke")
def oauth_revoke(
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Revoke OAuth tokens and disconnect app."""
    from .oauth import TokenStorage

    if not force:
        if not typer.confirm("Revoke OAuth tokens and disconnect?"):
            console.print("[yellow]Cancelled[/yellow]")
            raise typer.Exit(0)

    storage = TokenStorage()
    storage.clear_oauth()

    console.print("[green]OAuth tokens revoked.[/green]")
    console.print("[dim]Run 'maxlevel oauth connect' to reconnect.[/dim]")


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
                return {"success": False, "error": "Not logged in. Run 'maxlevel browser capture' first."}

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


@workflows_app.command("create-for-ai")
def workflows_create_for_ai(
    name: str = typer.Argument(..., help="Workflow name"),
    trigger: str = typer.Option(
        "manual",
        "--trigger",
        "-t",
        help="Trigger type: conversation_ai, voice_ai, manual",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-n", help="Show steps without executing"
    ),
):
    """Create a workflow for AI agent triggers via browser automation.

    Since GHL has no API for workflow creation, this uses browser
    automation to create workflows through the GHL UI.

    Requires Chrome with Claude-in-Chrome extension.

    Examples:
        ghl workflows create-for-ai "AI Lead Capture" --trigger conversation_ai
        ghl workflows create-for-ai "Voice Follow-up" -t voice_ai --dry-run
    """
    from .browser.chrome_mcp.executor import create_workflow_plan

    trigger_display = {
        "conversation_ai": "Conversation AI",
        "voice_ai": "Voice AI",
        "manual": "Manual/Contact Added",
    }.get(trigger, trigger)

    console.print(
        Panel(
            f"[bold]Creating workflow via browser automation[/bold]\n\n"
            f"Name: {name}\n"
            f"Trigger: {trigger_display}\n\n"
            "[dim]This will automate the GHL workflow builder.[/dim]",
            title="Workflow Creator",
        )
    )

    # Generate the plan (tab_id=0 is placeholder - Claude Code provides real ID)
    plan = create_workflow_plan(tab_id=0, name=name, trigger=trigger)

    if dry_run:
        plan.print_plan(console)
        console.print("[yellow]Dry run - no actions taken[/yellow]")
        console.print(
            "\n[dim]To execute, run without --dry-run flag and ensure Chrome "
            "with Claude-in-Chrome is running.[/dim]"
        )
        return

    # Show execution instructions
    console.print("\n[bold cyan]Browser Automation Required[/bold cyan]\n")
    console.print("Prerequisites:")
    console.print("  1. Chrome with Claude-in-Chrome extension installed")
    console.print("  2. Logged into GHL in the browser")
    console.print("  3. Running within a Claude Code session\n")

    plan.print_plan(console)

    console.print(
        Panel(
            "[bold]Next Steps:[/bold]\n\n"
            "Claude Code will execute these browser automation steps.\n"
            "The workflow will be created in your GHL account.\n\n"
            "[dim]Use --dry-run to preview steps without execution.[/dim]",
            title="Ready for Execution",
        )
    )


@workflows_app.command("connect-ai")
def workflows_connect_ai(
    workflow_name: str = typer.Argument(..., help="Workflow name"),
    agent_name: str = typer.Argument(..., help="AI agent name"),
    agent_type: str = typer.Option(
        "conversation",
        "--type",
        "-t",
        help="Agent type: conversation or voice",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-n", help="Show steps without executing"
    ),
):
    """Connect a workflow to an AI agent via browser automation.

    Links an existing workflow to a Conversation AI or Voice AI agent.
    This enables the AI to trigger workflows based on conversation outcomes.

    Requires Chrome with Claude-in-Chrome extension.

    Examples:
        ghl workflows connect-ai "AI Lead Capture" "Support Bot"
        ghl workflows connect-ai "Voice Follow-up" "Sales Agent" --type voice
    """
    from .browser.chrome_mcp.executor import connect_workflow_plan

    type_display = "Conversation AI" if agent_type == "conversation" else "Voice AI"

    console.print(
        Panel(
            f"[bold]Connecting workflow to AI agent[/bold]\n\n"
            f"Workflow: {workflow_name}\n"
            f"Agent: {agent_name}\n"
            f"Type: {type_display}\n\n"
            "[dim]This will automate the agent configuration in GHL.[/dim]",
            title="Workflow Connector",
        )
    )

    # Generate the plan
    plan = connect_workflow_plan(
        tab_id=0,
        workflow_name=workflow_name,
        agent_name=agent_name,
        agent_type=agent_type,
    )

    if dry_run:
        plan.print_plan(console)
        console.print("[yellow]Dry run - no actions taken[/yellow]")
        console.print(
            "\n[dim]To execute, run without --dry-run flag and ensure Chrome "
            "with Claude-in-Chrome is running.[/dim]"
        )
        return

    # Show execution instructions
    console.print("\n[bold cyan]Browser Automation Required[/bold cyan]\n")
    console.print("Prerequisites:")
    console.print("  1. Chrome with Claude-in-Chrome extension installed")
    console.print("  2. Logged into GHL in the browser")
    console.print("  3. Running within a Claude Code session\n")

    plan.print_plan(console)

    console.print(
        Panel(
            "[bold]Next Steps:[/bold]\n\n"
            "Claude Code will execute these browser automation steps.\n"
            f"The workflow will be connected to agent '{agent_name}'.\n\n"
            "[dim]Use --dry-run to preview steps without execution.[/dim]",
            title="Ready for Execution",
        )
    )


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
# Conversation AI Commands
# ============================================================================


@ai_app.command("list")
def ai_list(
    limit: int = typer.Option(50, "--limit", "-l", help="Max agents to return"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """List all conversation AI agents."""
    from .api import GHLClient

    async def _list():
        async with GHLClient.from_session() as ghl:
            return await ghl.conversation_ai.list_agents(limit=limit)

    result = asyncio.run(_list())

    if json_output:
        _output_result(result, json_output=True)
    else:
        agents = result.get("agents", [])
        table = Table(title=f"Conversation AI Agents ({len(agents)})")
        table.add_column("ID", style="dim", max_width=24)
        table.add_column("Name", style="cyan")
        table.add_column("Model", style="yellow")
        table.add_column("Enabled", style="green")

        for a in agents:
            enabled = "[green]Yes[/green]" if a.get("enabled", False) else "[red]No[/red]"
            table.add_row(
                a.get("id", a.get("_id", ""))[:24],
                a.get("name", "-"),
                a.get("model", "-"),
                enabled,
            )

        console.print(table)


@ai_app.command("get")
def ai_get(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Get a conversation AI agent by ID."""
    from .api import GHLClient

    async def _get():
        async with GHLClient.from_session() as ghl:
            return await ghl.conversation_ai.get_agent(agent_id)

    result = asyncio.run(_get())
    _output_result(result, json_output)


@ai_app.command("create")
def ai_create(
    name: str = typer.Argument(..., help="Agent name"),
    prompt: str = typer.Option(None, "--prompt", "-p", help="System prompt"),
    model: str = typer.Option("gpt-4", "--model", "-m", help="AI model"),
    temperature: float = typer.Option(0.7, "--temperature", "-t", help="Temperature (0-1)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Create a new conversation AI agent."""
    from .api import GHLClient

    async def _create():
        async with GHLClient.from_session() as ghl:
            return await ghl.conversation_ai.create_agent(
                name=name,
                prompt=prompt,
                model=model,
                temperature=temperature,
            )

    result = asyncio.run(_create())
    _output_result(result, json_output)
    console.print("[green]Conversation AI agent created![/green]")


@ai_app.command("update")
def ai_update(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    name: str = typer.Option(None, "--name", "-n", help="New agent name"),
    prompt: str = typer.Option(None, "--prompt", "-p", help="New system prompt"),
    model: str = typer.Option(None, "--model", "-m", help="New AI model"),
    temperature: float = typer.Option(None, "--temperature", "-t", help="New temperature"),
    enabled: bool = typer.Option(None, "--enabled/--disabled", help="Enable/disable agent"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Update a conversation AI agent."""
    from .api import GHLClient

    async def _update():
        async with GHLClient.from_session() as ghl:
            return await ghl.conversation_ai.update_agent(
                agent_id,
                name=name,
                prompt=prompt,
                model=model,
                temperature=temperature,
                enabled=enabled,
            )

    result = asyncio.run(_update())
    _output_result(result, json_output)
    console.print("[green]Agent updated![/green]")


@ai_app.command("delete")
def ai_delete(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Delete a conversation AI agent."""
    from .api import GHLClient

    if not yes:
        confirm = typer.confirm(f"Delete agent {agent_id}?")
        if not confirm:
            console.print("[yellow]Aborted.[/yellow]")
            raise typer.Exit(0)

    async def _delete():
        async with GHLClient.from_session() as ghl:
            return await ghl.conversation_ai.delete_agent(agent_id)

    asyncio.run(_delete())
    console.print("[green]Agent deleted![/green]")


@ai_app.command("actions")
def ai_actions(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """List actions attached to an agent."""
    from .api import GHLClient

    async def _actions():
        async with GHLClient.from_session() as ghl:
            return await ghl.conversation_ai.list_actions(agent_id)

    result = asyncio.run(_actions())

    if json_output:
        _output_result(result, json_output=True)
    else:
        actions = result.get("actions", [])
        table = Table(title=f"Agent Actions ({len(actions)})")
        table.add_column("ID", style="dim", max_width=24)
        table.add_column("Type", style="yellow")
        table.add_column("Trigger", style="cyan")

        for a in actions:
            table.add_row(
                a.get("id", a.get("_id", ""))[:24],
                a.get("type", "-"),
                a.get("triggerCondition", "-"),
            )

        console.print(table)


@ai_app.command("attach-action")
def ai_attach_action(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    action_id: str = typer.Argument(..., help="Workflow/action ID to attach"),
    action_type: str = typer.Option("workflow", "--type", "-t", help="Action type"),
    trigger: str = typer.Option(None, "--trigger", help="Trigger condition"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Attach a workflow action to an agent."""
    from .api import GHLClient

    async def _attach():
        async with GHLClient.from_session() as ghl:
            return await ghl.conversation_ai.attach_action(
                agent_id, action_id, action_type=action_type, trigger_condition=trigger
            )

    result = asyncio.run(_attach())
    _output_result(result, json_output)
    console.print("[green]Action attached![/green]")


@ai_app.command("remove-action")
def ai_remove_action(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    action_id: str = typer.Argument(..., help="Action ID to remove"),
):
    """Remove an action from an agent."""
    from .api import GHLClient

    async def _remove():
        async with GHLClient.from_session() as ghl:
            return await ghl.conversation_ai.remove_action(agent_id, action_id)

    asyncio.run(_remove())
    console.print("[green]Action removed![/green]")


@ai_app.command("history")
def ai_history(
    agent_id: str = typer.Option(None, "--agent", "-a", help="Filter by agent ID"),
    contact_id: str = typer.Option(None, "--contact", "-c", help="Filter by contact ID"),
    limit: int = typer.Option(50, "--limit", "-l", help="Max results"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """View AI generation history (chat interactions)."""
    from .api import GHLClient

    async def _history():
        async with GHLClient.from_session() as ghl:
            return await ghl.conversation_ai.list_generations(
                agent_id=agent_id, contact_id=contact_id, limit=limit
            )

    result = asyncio.run(_history())

    if json_output:
        _output_result(result, json_output=True)
    else:
        generations = result.get("generations", [])
        table = Table(title=f"AI Generations ({len(generations)})")
        table.add_column("ID", style="dim", max_width=16)
        table.add_column("Agent", style="cyan", max_width=20)
        table.add_column("Contact", style="white", max_width=16)
        table.add_column("Created", style="yellow")

        for g in generations:
            table.add_row(
                g.get("id", g.get("_id", ""))[:16],
                g.get("agentId", "-")[:20],
                g.get("contactId", "-")[:16],
                g.get("createdAt", "-")[:19],
            )

        console.print(table)


@ai_app.command("settings")
def ai_settings(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Get Conversation AI settings for the current location."""
    from .api import GHLClient

    async def _settings():
        async with GHLClient.from_session() as ghl:
            return await ghl.conversation_ai.get_settings()

    result = asyncio.run(_settings())
    _output_result(result, json_output)


# ============================================================================
# Voice AI Commands
# ============================================================================


@voice_app.command("list")
def voice_list(
    limit: int = typer.Option(50, "--limit", "-l", help="Max agents to return"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """List all voice AI agents."""
    from .api import GHLClient

    async def _list():
        async with GHLClient.from_session() as ghl:
            return await ghl.voice_ai.list_agents(limit=limit)

    result = asyncio.run(_list())

    if json_output:
        _output_result(result, json_output=True)
    else:
        agents = result.get("agents", [])
        table = Table(title=f"Voice AI Agents ({len(agents)})")
        table.add_column("ID", style="dim", max_width=24)
        table.add_column("Name", style="cyan")
        table.add_column("Voice", style="yellow")
        table.add_column("Enabled", style="green")

        for a in agents:
            enabled = "[green]Yes[/green]" if a.get("enabled", False) else "[red]No[/red]"
            table.add_row(
                a.get("id", a.get("_id", ""))[:24],
                a.get("name", "-"),
                a.get("voiceId", "-")[:20] if a.get("voiceId") else "-",
                enabled,
            )

        console.print(table)


@voice_app.command("get")
def voice_get(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Get a voice AI agent by ID."""
    from .api import GHLClient

    async def _get():
        async with GHLClient.from_session() as ghl:
            return await ghl.voice_ai.get_agent(agent_id)

    result = asyncio.run(_get())
    _output_result(result, json_output)


@voice_app.command("create")
def voice_create(
    name: str = typer.Argument(..., help="Agent name"),
    voice_id: str = typer.Argument(..., help="Voice profile ID (use 'maxlevel voice voices' to list)"),
    prompt: str = typer.Option(None, "--prompt", "-p", help="System prompt"),
    greeting: str = typer.Option(None, "--greeting", "-g", help="Initial greeting"),
    model: str = typer.Option("gpt-4", "--model", "-m", help="AI model"),
    temperature: float = typer.Option(0.7, "--temperature", "-t", help="Temperature (0-1)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Create a new voice AI agent."""
    from .api import GHLClient

    async def _create():
        async with GHLClient.from_session() as ghl:
            return await ghl.voice_ai.create_agent(
                name=name,
                voice_id=voice_id,
                prompt=prompt,
                greeting=greeting,
                model=model,
                temperature=temperature,
            )

    result = asyncio.run(_create())
    _output_result(result, json_output)
    console.print("[green]Voice AI agent created![/green]")


@voice_app.command("update")
def voice_update(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    name: str = typer.Option(None, "--name", "-n", help="New agent name"),
    voice_id: str = typer.Option(None, "--voice", "-v", help="New voice profile ID"),
    prompt: str = typer.Option(None, "--prompt", "-p", help="New system prompt"),
    greeting: str = typer.Option(None, "--greeting", "-g", help="New greeting"),
    enabled: bool = typer.Option(None, "--enabled/--disabled", help="Enable/disable agent"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Update a voice AI agent."""
    from .api import GHLClient

    async def _update():
        async with GHLClient.from_session() as ghl:
            return await ghl.voice_ai.update_agent(
                agent_id,
                name=name,
                voice_id=voice_id,
                prompt=prompt,
                greeting=greeting,
                enabled=enabled,
            )

    result = asyncio.run(_update())
    _output_result(result, json_output)
    console.print("[green]Agent updated![/green]")


@voice_app.command("delete")
def voice_delete(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Delete a voice AI agent."""
    from .api import GHLClient

    if not yes:
        confirm = typer.confirm(f"Delete voice agent {agent_id}?")
        if not confirm:
            console.print("[yellow]Aborted.[/yellow]")
            raise typer.Exit(0)

    async def _delete():
        async with GHLClient.from_session() as ghl:
            return await ghl.voice_ai.delete_agent(agent_id)

    asyncio.run(_delete())
    console.print("[green]Voice agent deleted![/green]")


@voice_app.command("voices")
def voice_voices(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """List available voice profiles."""
    from .api import GHLClient

    async def _voices():
        async with GHLClient.from_session() as ghl:
            return await ghl.voice_ai.list_voices()

    result = asyncio.run(_voices())

    if json_output:
        _output_result(result, json_output=True)
    else:
        voices = result.get("voices", [])
        table = Table(title=f"Available Voices ({len(voices)})")
        table.add_column("ID", style="dim", max_width=30)
        table.add_column("Name", style="cyan")
        table.add_column("Preview URL", style="white", max_width=40)

        for v in voices:
            preview = v.get("previewUrl", v.get("preview_url", "-"))
            if preview and len(preview) > 40:
                preview = preview[:37] + "..."
            table.add_row(
                v.get("id", v.get("_id", ""))[:30],
                v.get("name", "-"),
                preview,
            )

        console.print(table)


@voice_app.command("calls")
def voice_calls(
    agent_id: str = typer.Option(None, "--agent", "-a", help="Filter by agent ID"),
    contact_id: str = typer.Option(None, "--contact", "-c", help="Filter by contact ID"),
    status: str = typer.Option(None, "--status", "-s", help="Filter by status"),
    limit: int = typer.Option(50, "--limit", "-l", help="Max results"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """List voice AI call logs."""
    from .api import GHLClient

    async def _calls():
        async with GHLClient.from_session() as ghl:
            return await ghl.voice_ai.list_calls(
                agent_id=agent_id, contact_id=contact_id, status=status, limit=limit
            )

    result = asyncio.run(_calls())

    if json_output:
        _output_result(result, json_output=True)
    else:
        calls = result.get("calls", [])
        table = Table(title=f"Voice AI Calls ({len(calls)})")
        table.add_column("ID", style="dim", max_width=20)
        table.add_column("Agent", style="cyan", max_width=16)
        table.add_column("Duration", style="yellow")
        table.add_column("Status", style="green")
        table.add_column("Date", style="white")

        for c in calls:
            duration = c.get("duration", 0)
            duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "-"
            status_val = c.get("status", "-")
            status_style = "green" if status_val == "completed" else "yellow"
            table.add_row(
                c.get("id", c.get("_id", ""))[:20],
                c.get("agentId", "-")[:16],
                duration_str,
                f"[{status_style}]{status_val}[/{status_style}]",
                c.get("createdAt", "-")[:19],
            )

        console.print(table)


@voice_app.command("transcript")
def voice_transcript(
    call_id: str = typer.Argument(..., help="Call ID"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Get transcript for a voice call."""
    from .api import GHLClient

    async def _transcript():
        async with GHLClient.from_session() as ghl:
            return await ghl.voice_ai.get_call(call_id)

    result = asyncio.run(_transcript())

    if json_output:
        _output_result(result, json_output=True)
    else:
        call = result.get("call", result)
        console.print(
            Panel(
                f"[bold]Call ID:[/bold] {call.get('id', call_id)}\n"
                f"[bold]Status:[/bold] {call.get('status', 'unknown')}\n"
                f"[bold]Duration:[/bold] {call.get('duration', 0)}s\n"
                f"[bold]Agent:[/bold] {call.get('agentId', 'unknown')}",
                title="Call Details",
            )
        )

        transcript = call.get("transcript", [])
        if transcript:
            console.print("\n[bold cyan]Transcript:[/bold cyan]")
            for entry in transcript:
                role = entry.get("role", "unknown")
                text = entry.get("text", entry.get("content", ""))
                style = "blue" if role == "assistant" else "white"
                console.print(f"  [{style}]{role.upper()}:[/{style}] {text}")
        else:
            console.print("\n[yellow]No transcript available[/yellow]")

        summary = call.get("summary")
        if summary:
            console.print(f"\n[bold]Summary:[/bold] {summary}")


@voice_app.command("actions")
def voice_actions(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """List actions for a voice agent."""
    from .api import GHLClient

    async def _actions():
        async with GHLClient.from_session() as ghl:
            return await ghl.voice_ai.list_actions(agent_id)

    result = asyncio.run(_actions())

    if json_output:
        _output_result(result, json_output=True)
    else:
        actions = result.get("actions", [])
        table = Table(title=f"Voice Agent Actions ({len(actions)})")
        table.add_column("ID", style="dim", max_width=24)
        table.add_column("Name", style="cyan")
        table.add_column("Type", style="yellow")
        table.add_column("Trigger", style="white")

        for a in actions:
            table.add_row(
                a.get("id", a.get("_id", ""))[:24],
                a.get("name", "-"),
                a.get("type", "-"),
                a.get("triggerCondition", "-"),
            )

        console.print(table)


@voice_app.command("add-action")
def voice_add_action(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    action_type: str = typer.Argument(..., help="Action type (workflow, webhook, transfer, hangup)"),
    name: str = typer.Argument(..., help="Action name"),
    trigger: str = typer.Option(None, "--trigger", "-t", help="Trigger condition"),
    workflow_id: str = typer.Option(None, "--workflow", "-w", help="Workflow ID (if type=workflow)"),
    webhook_url: str = typer.Option(None, "--webhook", help="Webhook URL (if type=webhook)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Add an action to a voice agent."""
    from .api import GHLClient

    async def _add():
        async with GHLClient.from_session() as ghl:
            return await ghl.voice_ai.create_action(
                agent_id,
                action_type=action_type,
                name=name,
                trigger_condition=trigger,
                workflow_id=workflow_id,
                webhook_url=webhook_url,
            )

    result = asyncio.run(_add())
    _output_result(result, json_output)
    console.print("[green]Action added![/green]")


@voice_app.command("remove-action")
def voice_remove_action(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    action_id: str = typer.Argument(..., help="Action ID to remove"),
):
    """Remove an action from a voice agent."""
    from .api import GHLClient

    async def _remove():
        async with GHLClient.from_session() as ghl:
            return await ghl.voice_ai.delete_action(agent_id, action_id)

    asyncio.run(_remove())
    console.print("[green]Action removed![/green]")


@voice_app.command("settings")
def voice_settings(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Get Voice AI settings for the current location."""
    from .api import GHLClient

    async def _settings():
        async with GHLClient.from_session() as ghl:
            return await ghl.voice_ai.get_settings()

    result = asyncio.run(_settings())
    _output_result(result, json_output)


@voice_app.command("phones")
def voice_phones(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """List phone numbers available for Voice AI."""
    from .api import GHLClient

    async def _phones():
        async with GHLClient.from_session() as ghl:
            return await ghl.voice_ai.list_phone_numbers()

    result = asyncio.run(_phones())

    if json_output:
        _output_result(result, json_output=True)
    else:
        phones = result.get("phoneNumbers", [])
        table = Table(title=f"Voice AI Phone Numbers ({len(phones)})")
        table.add_column("ID", style="dim", max_width=24)
        table.add_column("Number", style="cyan")
        table.add_column("Assigned To", style="yellow")

        for p in phones:
            table.add_row(
                p.get("id", p.get("_id", ""))[:24],
                p.get("phone", p.get("number", "-")),
                p.get("agentId", "-") if p.get("agentId") else "[dim]Unassigned[/dim]",
            )

        console.print(table)


# ============================================================================
# Agency Commands (Sub-Account Management)
# ============================================================================


@agency_app.command("list")
def agency_list(
    search: str = typer.Option(None, "--search", "-s", help="Search by location name"),
    limit: int = typer.Option(100, "--limit", "-l", help="Max locations to return"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """List all sub-accounts (locations) under the agency."""
    from .api import GHLClient

    async def _list():
        async with GHLClient.from_session() as ghl:
            return await ghl.agency.list_locations(limit=limit, search=search)

    result = asyncio.run(_list())

    if json_output:
        _output_result(result, json_output=True)
    else:
        locations = result.get("locations", [])
        table = Table(title=f"Sub-Accounts ({len(locations)})")
        table.add_column("ID", style="dim", max_width=24)
        table.add_column("Name", style="cyan")
        table.add_column("Email", style="white")
        table.add_column("Phone", style="green")
        table.add_column("Timezone", style="yellow")

        for loc in locations:
            table.add_row(
                loc.get("_id", loc.get("id", ""))[:24],
                loc.get("name", "-"),
                loc.get("email", "-"),
                loc.get("phone", "-"),
                loc.get("timezone", "-"),
            )

        console.print(table)


@agency_app.command("get")
def agency_get(
    location_id: str = typer.Argument(..., help="Sub-account/location ID"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Get details of a specific sub-account."""
    from .api import GHLClient

    async def _get():
        async with GHLClient.from_session() as ghl:
            return await ghl.agency.get_location(location_id)

    result = asyncio.run(_get())

    if json_output:
        _output_result(result, json_output=True)
    else:
        loc = result.get("location", result)
        console.print(
            Panel(
                f"[bold]Name:[/bold] {loc.get('name', 'N/A')}\n"
                f"[bold]ID:[/bold] {loc.get('_id', loc.get('id', 'N/A'))}\n"
                f"[bold]Email:[/bold] {loc.get('email', 'N/A')}\n"
                f"[bold]Phone:[/bold] {loc.get('phone', 'N/A')}\n"
                f"[bold]Address:[/bold] {loc.get('address', '')} {loc.get('city', '')} {loc.get('state', '')} {loc.get('postalCode', '')}\n"
                f"[bold]Country:[/bold] {loc.get('country', 'N/A')}\n"
                f"[bold]Website:[/bold] {loc.get('website', 'N/A')}\n"
                f"[bold]Timezone:[/bold] {loc.get('timezone', 'N/A')}",
                title="Sub-Account Details",
            )
        )


@agency_app.command("create")
def agency_create(
    name: str = typer.Argument(..., help="Business name for the sub-account"),
    email: str = typer.Option(None, "--email", "-e", help="Primary contact email"),
    phone: str = typer.Option(None, "--phone", "-p", help="Business phone (E.164 format)"),
    address: str = typer.Option(None, "--address", "-a", help="Street address"),
    city: str = typer.Option(None, "--city", help="City name"),
    state: str = typer.Option(None, "--state", help="State/province code"),
    postal_code: str = typer.Option(None, "--postal-code", "--zip", help="ZIP/postal code"),
    country: str = typer.Option("US", "--country", "-c", help="Country code"),
    website: str = typer.Option(None, "--website", "-w", help="Business website URL"),
    timezone: str = typer.Option("America/New_York", "--timezone", "-t", help="IANA timezone"),
    snapshot_id: str = typer.Option(None, "--snapshot", "-s", help="Snapshot ID to use as template"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Create a new sub-account.

    Requires Agency Pro plan ($497/mo). Creates a new sub-account under
    your agency that can be assigned to a client.

    Examples:
        ghl agency create "Acme Corp" --email acme@example.com --phone +15551234567
        ghl agency create "Test Client" --snapshot snapshot_id_here
    """
    from .api import GHLClient

    async def _create():
        async with GHLClient.from_session() as ghl:
            return await ghl.agency.create_location(
                name=name,
                email=email,
                phone=phone,
                address=address,
                city=city,
                state=state,
                postal_code=postal_code,
                country=country,
                website=website,
                timezone=timezone,
                snapshot_id=snapshot_id,
            )

    result = asyncio.run(_create())
    _output_result(result, json_output)
    console.print("[green]Sub-account created successfully![/green]")


@agency_app.command("update")
def agency_update(
    location_id: str = typer.Argument(..., help="Sub-account ID to update"),
    name: str = typer.Option(None, "--name", "-n", help="New business name"),
    email: str = typer.Option(None, "--email", "-e", help="New contact email"),
    phone: str = typer.Option(None, "--phone", "-p", help="New phone number"),
    address: str = typer.Option(None, "--address", "-a", help="New street address"),
    city: str = typer.Option(None, "--city", help="New city"),
    state: str = typer.Option(None, "--state", help="New state/province"),
    postal_code: str = typer.Option(None, "--postal-code", "--zip", help="New postal code"),
    country: str = typer.Option(None, "--country", "-c", help="New country code"),
    website: str = typer.Option(None, "--website", "-w", help="New website URL"),
    timezone: str = typer.Option(None, "--timezone", "-t", help="New timezone"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Update an existing sub-account."""
    from .api import GHLClient

    async def _update():
        async with GHLClient.from_session() as ghl:
            return await ghl.agency.update_location(
                location_id,
                name=name,
                email=email,
                phone=phone,
                address=address,
                city=city,
                state=state,
                postal_code=postal_code,
                country=country,
                website=website,
                timezone=timezone,
            )

    result = asyncio.run(_update())
    _output_result(result, json_output)
    console.print("[green]Sub-account updated![/green]")


@agency_app.command("delete")
def agency_delete(
    location_id: str = typer.Argument(..., help="Sub-account ID to delete"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Delete a sub-account.

    WARNING: This permanently deletes the sub-account and ALL its data.
    This action cannot be undone.
    """
    from .api import GHLClient

    if not yes:
        console.print(
            f"[red]WARNING: This will permanently delete sub-account {location_id} "
            "and ALL its data.[/red]"
        )
        confirm = typer.confirm(
            "Are you sure?",
            default=False,
        )
        if not confirm:
            console.print("[yellow]Aborted.[/yellow]")
            raise typer.Exit(0)

    async def _delete():
        async with GHLClient.from_session() as ghl:
            return await ghl.agency.delete_location(location_id)

    asyncio.run(_delete())
    console.print("[green]Sub-account deleted.[/green]")


@agency_app.command("snapshots")
def agency_snapshots(
    limit: int = typer.Option(50, "--limit", "-l", help="Max snapshots to return"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """List available snapshots (location templates)."""
    from .api import GHLClient

    async def _list():
        async with GHLClient.from_session() as ghl:
            return await ghl.agency.list_snapshots(limit=limit)

    result = asyncio.run(_list())

    if json_output:
        _output_result(result, json_output=True)
    else:
        snapshots = result.get("snapshots", [])
        table = Table(title=f"Location Snapshots ({len(snapshots)})")
        table.add_column("ID", style="dim", max_width=24)
        table.add_column("Name", style="cyan")
        table.add_column("Created", style="yellow")

        for s in snapshots:
            table.add_row(
                s.get("_id", s.get("id", ""))[:24],
                s.get("name", "-"),
                s.get("createdAt", "-")[:19] if s.get("createdAt") else "-",
            )

        console.print(table)


@agency_app.command("users")
def agency_users(
    location_id: str = typer.Option(None, "--location", "-l", help="Filter by location ID"),
    limit: int = typer.Option(50, "--limit", help="Max users to return"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """List users in the agency or a specific sub-account."""
    from .api import GHLClient

    async def _list():
        async with GHLClient.from_session() as ghl:
            return await ghl.agency.list_users(location_id=location_id, limit=limit)

    result = asyncio.run(_list())

    if json_output:
        _output_result(result, json_output=True)
    else:
        users = result.get("users", [])
        title = f"Users ({len(users)})"
        if location_id:
            title = f"Users in Location ({len(users)})"

        table = Table(title=title)
        table.add_column("ID", style="dim", max_width=24)
        table.add_column("Name", style="cyan")
        table.add_column("Email", style="white")
        table.add_column("Role", style="yellow")

        for u in users:
            name = f"{u.get('firstName', '')} {u.get('lastName', '')}".strip() or "-"
            table.add_row(
                u.get("_id", u.get("id", ""))[:24],
                name,
                u.get("email", "-"),
                u.get("role", "-"),
            )

        console.print(table)


@agency_app.command("invite")
def agency_invite(
    email: str = typer.Argument(..., help="User's email address"),
    first_name: str = typer.Argument(..., help="User's first name"),
    last_name: str = typer.Argument(..., help="User's last name"),
    role: str = typer.Option("user", "--role", "-r", help="User role (admin, user)"),
    location_id: str = typer.Option(None, "--location", "-l", help="Invite to specific sub-account"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Invite a user to the agency or a specific sub-account."""
    from .api import GHLClient

    async def _invite():
        async with GHLClient.from_session() as ghl:
            return await ghl.agency.invite_user(
                email=email,
                first_name=first_name,
                last_name=last_name,
                role=role,
                location_id=location_id,
            )

    result = asyncio.run(_invite())
    _output_result(result, json_output)
    console.print(f"[green]Invitation sent to {email}![/green]")


@agency_app.command("plan")
def agency_plan(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Get agency billing plan and sub-account limits."""
    from .api import GHLClient

    async def _plan():
        async with GHLClient.from_session() as ghl:
            plan = await ghl.agency.get_agency_plan()
            try:
                limits = await ghl.agency.get_location_limits()
            except Exception:
                limits = {}
            return {"plan": plan, "limits": limits}

    result = asyncio.run(_plan())

    if json_output:
        _output_result(result, json_output=True)
    else:
        plan_data = result.get("plan", {})
        limits = result.get("limits", {})

        console.print(
            Panel(
                f"[bold]Plan:[/bold] {plan_data.get('name', plan_data.get('planName', 'Unknown'))}\n"
                f"[bold]Status:[/bold] {plan_data.get('status', 'Unknown')}\n"
                f"[bold]Sub-Accounts Used:[/bold] {limits.get('used', '?')} / {limits.get('limit', '?')}\n"
                f"[bold]Remaining:[/bold] {limits.get('remaining', '?')}",
                title="Agency Plan",
            )
        )


# ============================================================================
# Hiring Funnel Commands
# ============================================================================

@hiring_app.command("setup")
def hiring_setup(
    role: str = typer.Option(None, "--role", "-r", help="Role/position name for context"),
    stages: str = typer.Option(None, "--stages", "-s", help="Comma-separated pipeline stage names"),
    dry_run: bool = typer.Option(True, "--dry-run/--apply", help="Dry-run (default) or apply changes"),
    output: str = typer.Option(None, "--output", "-o", help="Export blueprint to YAML file"),
):
    """Provision hiring funnel resources (tags, fields, values, AI agent) and show UI guide."""
    from .api import GHLClient
    from .hiring import get_hiring_blueprint, render_setup_guide
    from .hiring.template import SCREENING_AGENT_PROMPT

    stage_list = [s.strip() for s in stages.split(",")] if stages else None
    bp = get_hiring_blueprint(role=role, stages=stage_list)

    if output:
        from .blueprint.serialization import save_blueprint
        filepath = save_blueprint(bp, output)
        console.print(f"[green]Blueprint exported to {filepath}[/green]")
        return

    async def _setup():
        async with GHLClient.from_session() as ghl:
            from .blueprint.engine import provision_location
            result = await provision_location(ghl, bp, dry_run=dry_run)

            # Create AI screening agent if applying
            agent_result = None
            if not dry_run:
                try:
                    agent_result = await ghl.conversation_ai.create_agent(
                        name="Hiring Screener",
                        prompt=SCREENING_AGENT_PROMPT,
                        model="gpt-4",
                        temperature=0.5,
                    )
                except Exception as e:
                    result.errors.append(f"Failed to create screening agent: {e}")

            return result, agent_result

    try:
        with console.status("[bold cyan]Setting up hiring funnel...[/bold cyan]"):
            result, agent_result = asyncio.run(_setup())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    # Show provision plan
    from .blueprint.diff import render_plan
    render_plan(result, console)

    if dry_run:
        console.print("[dim]This is a dry run. Use --apply to execute changes.[/dim]")
    else:
        if result.errors:
            for err in result.errors:
                console.print(f"[red]Error: {err}[/red]")
        else:
            console.print("[green]Provisioned tags, custom fields, and custom values.[/green]")
        if agent_result:
            agent_id = agent_result.get("agent", {}).get("id", "unknown")
            console.print(f"[green]Created screening agent (ID: {agent_id})[/green]")

    # Show manual setup guide
    pipeline_stages = stage_list or None
    if pipeline_stages is None:
        from .hiring.template import DEFAULT_STAGES
        pipeline_stages = DEFAULT_STAGES
    render_setup_guide(provision_result=result, pipeline_stages=pipeline_stages, console=console)


@hiring_app.command("add-applicant")
def hiring_add_applicant(
    first_name: str = typer.Argument(..., help="Applicant first name"),
    last_name: str = typer.Argument(..., help="Applicant last name"),
    email: str = typer.Option(None, "--email", "-e", help="Email address"),
    phone: str = typer.Option(None, "--phone", "-p", help="Phone number (E.164)"),
    position: str = typer.Option(None, "--position", help="Position applied for"),
    resume: str = typer.Option(None, "--resume", help="Resume URL"),
    salary: float = typer.Option(None, "--salary", help="Desired salary"),
    source: str = typer.Option(None, "--source", help="Referral source"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Create a new applicant contact and opportunity in the hiring pipeline."""
    from .api import GHLClient

    async def _add():
        async with GHLClient.from_session() as ghl:
            # Build custom fields
            custom_fields: dict[str, Any] = {}
            if position:
                custom_fields["contact.position_applied"] = position
            if resume:
                custom_fields["contact.resume_url"] = resume
            if salary is not None:
                custom_fields["contact.desired_salary"] = salary
            if source:
                custom_fields["contact.referral_source"] = source

            # Create contact
            contact = await ghl.contacts.create(
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone,
                tags=["applicant"],
                custom_fields=custom_fields if custom_fields else None,
            )

            contact_id = contact.get("contact", {}).get("id", contact.get("id", ""))
            contact_name = f"{first_name} {last_name}"

            # Find Hiring Pipeline and first stage
            pipelines_resp = await ghl.opportunities.pipelines()
            pipelines = pipelines_resp.get("pipelines", [])
            hiring_pipeline = None
            for p in pipelines:
                if "hiring" in p.get("name", "").lower():
                    hiring_pipeline = p
                    break

            opp_result = None
            if hiring_pipeline and contact_id:
                pipeline_id = hiring_pipeline.get("id", hiring_pipeline.get("_id", ""))
                stages = hiring_pipeline.get("stages", [])
                first_stage_id = stages[0].get("id", stages[0].get("_id", "")) if stages else ""

                if pipeline_id and first_stage_id:
                    opp_result = await ghl.opportunities.create(
                        pipeline_id=pipeline_id,
                        stage_id=first_stage_id,
                        contact_id=contact_id,
                        name=f"{contact_name} - {position or 'Applicant'}",
                    )

            return {"contact": contact, "opportunity": opp_result}

    try:
        result = asyncio.run(_add())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    if json_output:
        _output_result(result, json_output=True)
    else:
        contact_data = result.get("contact", {})
        contact_id = contact_data.get("contact", {}).get("id", contact_data.get("id", "N/A"))
        console.print(f"[green]Applicant created![/green] Contact ID: {contact_id}")
        if result.get("opportunity"):
            opp_id = result["opportunity"].get("opportunity", {}).get("id",
                     result["opportunity"].get("id", "N/A"))
            console.print(f"  Opportunity ID: {opp_id}")
        else:
            console.print("  [yellow]No hiring pipeline found - create one via 'maxlevel hiring setup'[/yellow]")


@hiring_app.command("list")
def hiring_list(
    stage: str = typer.Option(None, "--stage", "-s", help="Filter by stage name"),
    limit: int = typer.Option(20, "--limit", "-l", help="Max results"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """List applicants in the hiring pipeline."""
    from .api import GHLClient

    async def _list():
        async with GHLClient.from_session() as ghl:
            # Find hiring pipeline
            pipelines_resp = await ghl.opportunities.pipelines()
            pipelines = pipelines_resp.get("pipelines", [])
            hiring_pipeline = None
            for p in pipelines:
                if "hiring" in p.get("name", "").lower():
                    hiring_pipeline = p
                    break

            if not hiring_pipeline:
                return {"error": "No hiring pipeline found", "opportunities": []}

            pipeline_id = hiring_pipeline.get("id", hiring_pipeline.get("_id", ""))
            stages = {
                s.get("id", s.get("_id", "")): s.get("name", "")
                for s in hiring_pipeline.get("stages", [])
            }

            # Filter by stage if specified
            target_stage_id = None
            if stage:
                for sid, sname in stages.items():
                    if stage.lower() in sname.lower():
                        target_stage_id = sid
                        break

            opps_resp = await ghl.opportunities.list(
                pipeline_id=pipeline_id,
                stage_id=target_stage_id,
                limit=limit,
            )

            # Enrich with stage names
            opps = opps_resp.get("opportunities", [])
            for opp in opps:
                opp["_stage_name"] = stages.get(opp.get("pipelineStageId", ""), "Unknown")

            return {"opportunities": opps, "stages": stages, "pipeline_id": pipeline_id}

    try:
        result = asyncio.run(_list())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    if result.get("error"):
        console.print(f"[red]{result['error']}[/red]")
        raise typer.Exit(1)

    if json_output:
        _output_result(result, json_output=True)
    else:
        opps = result.get("opportunities", [])
        table = Table(title=f"Hiring Pipeline Applicants ({len(opps)})")
        table.add_column("ID", style="dim", max_width=24)
        table.add_column("Name", style="cyan")
        table.add_column("Stage", style="yellow")
        table.add_column("Status", style="white")
        table.add_column("Value", style="green")

        for opp in opps:
            table.add_row(
                opp.get("id", opp.get("_id", ""))[:24],
                opp.get("name", "-"),
                opp.get("_stage_name", "Unknown"),
                opp.get("status", "-"),
                str(opp.get("monetaryValue", "-")),
            )

        console.print(table)


@hiring_app.command("advance")
def hiring_advance(
    opp_id: str = typer.Argument(..., help="Opportunity ID"),
    stage_name: str = typer.Option(None, "--stage", "-s", help="Target stage name (default: next stage)"),
):
    """Move an applicant to the next pipeline stage or a specific stage."""
    from .api import GHLClient

    async def _advance():
        async with GHLClient.from_session() as ghl:
            # Get current opportunity
            opp = await ghl.opportunities.get(opp_id)
            opp_data = opp.get("opportunity", opp)
            current_stage_id = opp_data.get("pipelineStageId", "")
            pipeline_id = opp_data.get("pipelineId", "")
            contact_id = opp_data.get("contactId", "")

            # Get pipeline stages
            pipelines_resp = await ghl.opportunities.pipelines()
            pipeline = None
            for p in pipelines_resp.get("pipelines", []):
                if p.get("id", p.get("_id", "")) == pipeline_id:
                    pipeline = p
                    break

            if not pipeline:
                return {"error": "Pipeline not found"}

            stages = pipeline.get("stages", [])

            if stage_name:
                # Find target stage by name
                target = None
                for s in stages:
                    if stage_name.lower() in s.get("name", "").lower():
                        target = s
                        break
                if not target:
                    return {"error": f"Stage '{stage_name}' not found"}
                target_stage_id = target.get("id", target.get("_id", ""))
                target_name = target.get("name", "")
            else:
                # Find next stage
                current_idx = None
                for i, s in enumerate(stages):
                    if s.get("id", s.get("_id", "")) == current_stage_id:
                        current_idx = i
                        break

                if current_idx is None or current_idx >= len(stages) - 1:
                    return {"error": "Already at last stage or stage not found"}

                target = stages[current_idx + 1]
                target_stage_id = target.get("id", target.get("_id", ""))
                target_name = target.get("name", "")

            result = await ghl.opportunities.move_stage(opp_id, target_stage_id)

            # Update tags based on stage
            if contact_id:
                lower_name = target_name.lower()
                if "interview" in lower_name:
                    try:
                        await ghl.contacts.add_tag(contact_id, "interview-scheduled")
                    except Exception:
                        pass
                elif "offer" in lower_name:
                    try:
                        await ghl.contacts.add_tag(contact_id, "offer-extended")
                    except Exception:
                        pass
                elif "screening" in lower_name:
                    try:
                        await ghl.contacts.add_tag(contact_id, "screening")
                    except Exception:
                        pass

            return {"result": result, "target_stage": target_name}

    try:
        result = asyncio.run(_advance())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    if result.get("error"):
        console.print(f"[red]{result['error']}[/red]")
        raise typer.Exit(1)

    console.print(f"[green]Moved to stage: {result['target_stage']}[/green]")


@hiring_app.command("reject")
def hiring_reject(
    opp_id: str = typer.Argument(..., help="Opportunity ID"),
    reason: str = typer.Option(None, "--reason", "-r", help="Rejection reason (added as note)"),
):
    """Reject an applicant - moves to Rejected stage and marks as lost."""
    from .api import GHLClient

    async def _reject():
        async with GHLClient.from_session() as ghl:
            # Get opportunity for contact ID and pipeline
            opp = await ghl.opportunities.get(opp_id)
            opp_data = opp.get("opportunity", opp)
            contact_id = opp_data.get("contactId", "")
            pipeline_id = opp_data.get("pipelineId", "")

            # Find Rejected stage
            pipelines_resp = await ghl.opportunities.pipelines()
            rejected_stage_id = None
            for p in pipelines_resp.get("pipelines", []):
                if p.get("id", p.get("_id", "")) == pipeline_id:
                    for s in p.get("stages", []):
                        if "reject" in s.get("name", "").lower():
                            rejected_stage_id = s.get("id", s.get("_id", ""))
                            break
                    break

            warnings = []

            # Move to rejected stage if found
            if rejected_stage_id:
                await ghl.opportunities.move_stage(opp_id, rejected_stage_id)
            else:
                warnings.append("No 'Rejected' stage found in pipeline - skipped stage move")

            # Mark as lost
            await ghl.opportunities.mark_lost(opp_id)

            # Update tags
            if contact_id:
                try:
                    await ghl.contacts.add_tag(contact_id, "rejected")
                    await ghl.contacts.remove_tag(contact_id, "applicant")
                except Exception:
                    warnings.append("Failed to update contact tags")

                # Add rejection note
                if reason:
                    try:
                        await ghl.contacts.add_note(contact_id, f"Rejection reason: {reason}")
                    except Exception:
                        warnings.append("Failed to add rejection note")

            return {"status": "rejected", "warnings": warnings}

    try:
        result = asyncio.run(_reject())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    console.print("[yellow]Applicant rejected.[/yellow]")
    if reason:
        console.print(f"  Reason: {reason}")
    for w in result.get("warnings", []):
        console.print(f"  [yellow]Warning: {w}[/yellow]")


@hiring_app.command("hire")
def hiring_hire(
    opp_id: str = typer.Argument(..., help="Opportunity ID"),
    start_date: str = typer.Option(None, "--start-date", help="Start date (YYYY-MM-DD)"),
    salary: float = typer.Option(None, "--salary", help="Offered salary"),
):
    """Hire an applicant - moves to Hired stage and marks as won."""
    from .api import GHLClient

    async def _hire():
        async with GHLClient.from_session() as ghl:
            # Get opportunity
            opp = await ghl.opportunities.get(opp_id)
            opp_data = opp.get("opportunity", opp)
            contact_id = opp_data.get("contactId", "")
            pipeline_id = opp_data.get("pipelineId", "")

            # Find Hired stage
            pipelines_resp = await ghl.opportunities.pipelines()
            hired_stage_id = None
            for p in pipelines_resp.get("pipelines", []):
                if p.get("id", p.get("_id", "")) == pipeline_id:
                    for s in p.get("stages", []):
                        if "hired" in s.get("name", "").lower():
                            hired_stage_id = s.get("id", s.get("_id", ""))
                            break
                    break

            warnings = []

            # Move to hired stage
            if hired_stage_id:
                await ghl.opportunities.move_stage(opp_id, hired_stage_id)
            else:
                warnings.append("No 'Hired' stage found in pipeline - skipped stage move")

            # Mark as won
            await ghl.opportunities.mark_won(opp_id)

            # Update tags
            if contact_id:
                try:
                    await ghl.contacts.add_tag(contact_id, "hired")
                    await ghl.contacts.remove_tag(contact_id, "applicant")
                except Exception:
                    warnings.append("Failed to update contact tags")

                # Update custom fields
                updates: dict[str, Any] = {}
                if start_date:
                    updates["contact.available_start_date"] = start_date
                if salary is not None:
                    updates["contact.desired_salary"] = salary
                if updates:
                    try:
                        await ghl.contacts.update(contact_id, custom_fields=updates)
                    except Exception:
                        warnings.append("Failed to update custom fields")

                # Add hire note
                note_parts = ["Applicant hired!"]
                if start_date:
                    note_parts.append(f"Start date: {start_date}")
                if salary is not None:
                    note_parts.append(f"Salary: ${salary:,.2f}")
                try:
                    await ghl.contacts.add_note(contact_id, " ".join(note_parts))
                except Exception:
                    warnings.append("Failed to add hire note")

            return {"status": "hired", "warnings": warnings}

    try:
        result = asyncio.run(_hire())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    console.print("[green]Applicant hired![/green]")
    if start_date:
        console.print(f"  Start date: {start_date}")
    if salary is not None:
        console.print(f"  Salary: ${salary:,.2f}")
    for w in result.get("warnings", []):
        console.print(f"  [yellow]Warning: {w}[/yellow]")


@hiring_app.command("status")
def hiring_status(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Show hiring funnel dashboard - counts per stage."""
    from .api import GHLClient

    async def _status():
        async with GHLClient.from_session() as ghl:
            pipelines_resp = await ghl.opportunities.pipelines()
            pipelines = pipelines_resp.get("pipelines", [])
            hiring_pipeline = None
            for p in pipelines:
                if "hiring" in p.get("name", "").lower():
                    hiring_pipeline = p
                    break

            if not hiring_pipeline:
                return {"error": "No hiring pipeline found"}

            pipeline_id = hiring_pipeline.get("id", hiring_pipeline.get("_id", ""))
            stages = hiring_pipeline.get("stages", [])

            # Get all opportunities
            opps_resp = await ghl.opportunities.list(pipeline_id=pipeline_id, limit=100)
            opps = opps_resp.get("opportunities", [])

            # Count per stage
            stage_counts: dict[str, int] = {}
            stage_names: dict[str, str] = {}
            for s in stages:
                sid = s.get("id", s.get("_id", ""))
                sname = s.get("name", "")
                stage_names[sid] = sname
                stage_counts[sname] = 0

            total = len(opps)
            active = 0
            hired = 0
            rejected = 0

            for opp in opps:
                stage_id = opp.get("pipelineStageId", "")
                sname = stage_names.get(stage_id, "Unknown")
                stage_counts[sname] = stage_counts.get(sname, 0) + 1

                status = opp.get("status", "")
                if status == "open":
                    active += 1
                elif status == "won":
                    hired += 1
                elif status == "lost":
                    rejected += 1

            return {
                "stage_counts": stage_counts,
                "total": total,
                "active": active,
                "hired": hired,
                "rejected": rejected,
            }

    try:
        result = asyncio.run(_status())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    if result.get("error"):
        console.print(f"[red]{result['error']}[/red]")
        raise typer.Exit(1)

    if json_output:
        _output_result(result, json_output=True)
    else:
        # Summary panel
        console.print(Panel(
            f"[bold]Total:[/bold] {result['total']}  |  "
            f"[green]Active:[/green] {result['active']}  |  "
            f"[cyan]Hired:[/cyan] {result['hired']}  |  "
            f"[red]Rejected:[/red] {result['rejected']}",
            title="Hiring Dashboard",
        ))

        # Stage breakdown
        table = Table(title="Applicants by Stage")
        table.add_column("Stage", style="cyan")
        table.add_column("Count", style="bold", justify="right")

        for stage_name, count in result.get("stage_counts", {}).items():
            style = ""
            if "hired" in stage_name.lower():
                style = "green"
            elif "reject" in stage_name.lower():
                style = "red"
            table.add_row(stage_name, f"[{style}]{count}[/{style}]" if style else str(count))

        console.print(table)


@hiring_app.command("audit")
def hiring_audit(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Audit the current location against the hiring funnel blueprint."""
    from .api import GHLClient
    from .hiring import get_hiring_blueprint

    bp = get_hiring_blueprint()

    async def _audit():
        async with GHLClient.from_session() as ghl:
            from .blueprint.engine import audit_location
            return await audit_location(ghl, bp)

    try:
        with console.status("[bold cyan]Auditing hiring funnel...[/bold cyan]"):
            result = asyncio.run(_audit())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

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


@hiring_app.command("serve")
def hiring_serve(
    port: int = typer.Option(8021, "--port", "-p", help="Port to run on"),
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind to"),
):
    """Launch the hiring tool web UI."""
    try:
        import uvicorn
    except ImportError:
        console.print("[red]Missing dependencies. Install with: pip install -e '.[hiring]'[/red]")
        raise typer.Exit(1)

    console.print(f"[bold cyan]Starting Hiring Tool at http://{host}:{port}[/bold cyan]")
    uvicorn.run("hiring_tool.app:app", host=host, port=port, reload=True)


# ============================================================================
# CRM Commands
# ============================================================================


@crm_app.command("serve")
def crm_serve(
    port: int = typer.Option(8020, "--port", "-p", help="Port to run on"),
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind to"),
):
    """Launch the CRM platform web UI."""
    try:
        import uvicorn
    except ImportError:
        console.print("[red]Missing dependencies. Install with: pip install -e '.[crm]'[/red]")
        raise typer.Exit(1)

    console.print(f"[bold cyan]Starting CRM Platform at http://{host}:{port}[/bold cyan]")
    uvicorn.run("crm.app:app", host=host, port=port, reload=True)


# ============================================================================
# Workflow Builder Commands
# ============================================================================

builder_app = typer.Typer(help="Visual workflow automation builder")
app.add_typer(builder_app, name="builder")


@builder_app.command("serve")
def builder_serve(
    port: int = typer.Option(8022, "--port", "-p", help="Port to run on"),
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind to"),
):
    """Launch the Workflow Builder web UI."""
    try:
        import uvicorn
    except ImportError:
        console.print("[red]Missing dependencies. Install with: pip install -e '.[workflows]'[/red]")
        raise typer.Exit(1)

    console.print(f"[bold cyan]Starting Workflow Builder at http://{host}:{port}[/bold cyan]")
    uvicorn.run("workflows.app:app", host=host, port=port, reload=True)


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


# ============================================================================
# Dashboard Commands
# ============================================================================


@dashboard_app.command("serve")
def dashboard_serve(
    port: int = typer.Option(8023, "--port", "-p", help="Port to run on"),
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind to"),
):
    """Launch the unified dashboard web UI."""
    try:
        import uvicorn
    except ImportError:
        console.print("[red]Missing dependencies. Install with: pip install -e '.[dashboard]'[/red]")
        raise typer.Exit(1)

    console.print(f"[bold cyan]Starting Dashboard at http://{host}:{port}[/bold cyan]")
    uvicorn.run("dashboard.app:app", host=host, port=port, reload=True)


@app.command("serve-all")
def serve_all(
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind to"),
):
    """Launch all apps concurrently (Dashboard, CRM, Hiring, Workflows)."""
    import subprocess
    import sys

    apps = [
        ("dashboard.app:app", 8023, "Dashboard"),
        ("crm.app:app", 8020, "CRM"),
        ("hiring_tool.app:app", 8021, "Hiring"),
        ("workflows.app:app", 8022, "Workflows"),
    ]

    console.print("[bold cyan]Starting all MaxLevel apps...[/bold cyan]")
    for module, port, name in apps:
        console.print(f"  {name:12s} → http://{host}:{port}")

    processes = []
    for module, port, name in apps:
        p = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", module,
             "--host", host, "--port", str(port), "--reload"],
        )
        processes.append(p)

    try:
        for p in processes:
            p.wait()
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down all apps...[/yellow]")
        for p in processes:
            p.terminate()
        for p in processes:
            p.wait(timeout=5)


@app.command()
def version():
    """Show version information."""
    from . import __version__

    console.print(f"MaxLevel v{__version__}")


if __name__ == "__main__":
    app()
