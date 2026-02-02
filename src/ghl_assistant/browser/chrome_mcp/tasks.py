"""GHL-specific browser tasks for Chrome MCP automation.

This module provides high-level task definitions for common GHL operations
that require browser automation, such as:
- Login flow
- Token capture from network requests
- UI-based operations when API is unavailable
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .agent import ChromeMCPAgent


@dataclass
class TaskStep:
    """A single step in a browser task."""

    name: str
    description: str
    command: dict[str, Any]
    wait_after: float = 0.5
    screenshot_after: bool = False
    required: bool = True


@dataclass
class TaskResult:
    """Result of executing a browser task."""

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    steps_completed: int = 0


class GHLBrowserTasks:
    """GHL-specific browser automation tasks.

    This class provides task definitions that can be executed through Chrome MCP.
    Each task returns a sequence of steps that Claude Code can execute.

    Usage:
        tasks = GHLBrowserTasks(tab_id=123)

        # Get login steps
        steps = tasks.login("user@example.com", "password")

        # Get token capture steps
        steps = tasks.capture_api_token()

        # Get contact creation steps (for when API is unavailable)
        steps = tasks.create_contact_via_ui(
            first_name="John",
            last_name="Doe",
            email="john@example.com"
        )
    """

    GHL_BASE_URL = "https://app.gohighlevel.com"
    GHL_API_DOMAIN = "backend.leadconnectorhq.com"

    def __init__(self, tab_id: int):
        """Initialize with Chrome MCP tab ID.

        Args:
            tab_id: Tab ID from tabs_context_mcp
        """
        self.tab_id = tab_id
        self.agent = ChromeMCPAgent(tab_id)

    # =========================================================================
    # Authentication Tasks
    # =========================================================================

    def login(self, email: str, password: str) -> list[TaskStep]:
        """Generate steps for GHL login flow.

        Args:
            email: User email address
            password: User password

        Returns:
            List of TaskSteps to execute the login
        """
        return [
            TaskStep(
                name="navigate_login",
                description="Navigate to GHL login page",
                command=self.agent.navigate(f"{self.GHL_BASE_URL}/login"),
                wait_after=2.0,
            ),
            TaskStep(
                name="screenshot_login_page",
                description="Capture login page state",
                command=self.agent.screenshot(),
            ),
            TaskStep(
                name="find_email_field",
                description="Find email input field",
                command=self.agent.find_elements("email input field"),
            ),
            # Note: After finding, the ref will be used to fill
            TaskStep(
                name="type_email",
                description=f"Enter email: {email}",
                command=self.agent.type_text(email),
                wait_after=0.3,
            ),
            TaskStep(
                name="press_tab",
                description="Tab to password field",
                command=self.agent.press_key("Tab"),
            ),
            TaskStep(
                name="type_password",
                description="Enter password",
                command=self.agent.type_text(password),
                wait_after=0.3,
            ),
            TaskStep(
                name="find_submit",
                description="Find sign in button",
                command=self.agent.find_elements("sign in button"),
            ),
            TaskStep(
                name="click_submit",
                description="Click sign in",
                command=self.agent.press_key("Enter"),
                wait_after=3.0,
                screenshot_after=True,
            ),
            TaskStep(
                name="verify_login",
                description="Verify login success",
                command=self.agent.screenshot(),
            ),
        ]

    def logout(self) -> list[TaskStep]:
        """Generate steps for GHL logout.

        Returns:
            List of TaskSteps to execute logout
        """
        return [
            TaskStep(
                name="find_profile_menu",
                description="Find profile/settings menu",
                command=self.agent.find_elements("profile menu or settings dropdown"),
            ),
            TaskStep(
                name="click_profile_menu",
                description="Click profile menu",
                command=self.agent.press_key("Enter"),
                wait_after=0.5,
            ),
            TaskStep(
                name="find_logout",
                description="Find logout option",
                command=self.agent.find_elements("logout button or sign out"),
            ),
            TaskStep(
                name="click_logout",
                description="Click logout",
                command=self.agent.press_key("Enter"),
                wait_after=2.0,
            ),
            TaskStep(
                name="confirm_logout",
                description="Verify logged out",
                command=self.agent.screenshot(),
            ),
        ]

    # =========================================================================
    # Token Capture Tasks
    # =========================================================================

    def capture_api_token(self) -> list[TaskStep]:
        """Generate steps to capture API token from network requests.

        This task navigates to a page that makes authenticated API calls
        and captures the bearer token from the request headers.

        Returns:
            List of TaskSteps to capture the token
        """
        return [
            TaskStep(
                name="navigate_dashboard",
                description="Navigate to GHL dashboard",
                command=self.agent.navigate(self.GHL_BASE_URL),
                wait_after=3.0,
            ),
            TaskStep(
                name="wait_for_api_calls",
                description="Wait for API calls to complete",
                command=self.agent.wait(2.0),
            ),
            TaskStep(
                name="capture_network",
                description="Capture network requests to GHL API",
                command=self.agent.get_network_requests(
                    url_pattern=self.GHL_API_DOMAIN,
                    limit=50,
                ),
            ),
            TaskStep(
                name="extract_token_js",
                description="Extract token from localStorage/sessionStorage",
                command=self.agent.execute_js("""
                    (function() {
                        // Check localStorage
                        for (let i = 0; i < localStorage.length; i++) {
                            const key = localStorage.key(i);
                            const value = localStorage.getItem(key);
                            if (key.includes('token') || key.includes('auth')) {
                                console.log('TOKEN_FOUND:', key, '=', value.substring(0, 50));
                            }
                        }
                        // Check for common GHL token locations
                        if (window.__NUXT__) {
                            console.log('NUXT_STATE:', JSON.stringify(window.__NUXT__.state?.auth || {}));
                        }
                        return 'Token extraction complete';
                    })()
                """),
            ),
            TaskStep(
                name="read_console",
                description="Read console for extracted tokens",
                command=self.agent.get_console_messages(
                    pattern="TOKEN_FOUND|NUXT_STATE"
                ),
            ),
        ]

    # =========================================================================
    # Navigation Tasks
    # =========================================================================

    def navigate_to_contacts(self) -> list[TaskStep]:
        """Generate steps to navigate to contacts page.

        Returns:
            List of TaskSteps to navigate to contacts
        """
        return [
            TaskStep(
                name="navigate_contacts",
                description="Navigate to contacts page",
                command=self.agent.navigate(f"{self.GHL_BASE_URL}/contacts"),
                wait_after=2.0,
            ),
            TaskStep(
                name="verify_contacts_page",
                description="Verify contacts page loaded",
                command=self.agent.screenshot(),
            ),
        ]

    def navigate_to_conversations(self) -> list[TaskStep]:
        """Generate steps to navigate to conversations page."""
        return [
            TaskStep(
                name="navigate_conversations",
                description="Navigate to conversations page",
                command=self.agent.navigate(f"{self.GHL_BASE_URL}/conversations"),
                wait_after=2.0,
            ),
            TaskStep(
                name="verify_conversations_page",
                description="Verify conversations page loaded",
                command=self.agent.screenshot(),
            ),
        ]

    def navigate_to_settings(self) -> list[TaskStep]:
        """Generate steps to navigate to settings page."""
        return [
            TaskStep(
                name="navigate_settings",
                description="Navigate to settings page",
                command=self.agent.navigate(f"{self.GHL_BASE_URL}/settings"),
                wait_after=2.0,
            ),
            TaskStep(
                name="verify_settings_page",
                description="Verify settings page loaded",
                command=self.agent.screenshot(),
            ),
        ]

    # =========================================================================
    # Contact Tasks (UI Fallback)
    # =========================================================================

    def create_contact_via_ui(
        self,
        first_name: str,
        last_name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
    ) -> list[TaskStep]:
        """Generate steps to create a contact via UI.

        This is a fallback for when API access is unavailable.

        Args:
            first_name: Contact first name
            last_name: Contact last name
            email: Contact email
            phone: Contact phone

        Returns:
            List of TaskSteps to create the contact
        """
        steps = [
            TaskStep(
                name="navigate_contacts",
                description="Navigate to contacts page",
                command=self.agent.navigate(f"{self.GHL_BASE_URL}/contacts"),
                wait_after=2.0,
            ),
            TaskStep(
                name="find_add_button",
                description="Find add contact button",
                command=self.agent.find_elements("add contact button or create contact"),
            ),
            TaskStep(
                name="wait_for_modal",
                description="Wait for contact form modal",
                command=self.agent.wait(1.0),
            ),
            TaskStep(
                name="screenshot_form",
                description="Capture contact form",
                command=self.agent.screenshot(),
            ),
            TaskStep(
                name="find_first_name",
                description="Find first name field",
                command=self.agent.find_elements("first name input"),
            ),
            TaskStep(
                name="enter_first_name",
                description=f"Enter first name: {first_name}",
                command=self.agent.type_text(first_name),
            ),
        ]

        if last_name:
            steps.extend([
                TaskStep(
                    name="find_last_name",
                    description="Find last name field",
                    command=self.agent.find_elements("last name input"),
                ),
                TaskStep(
                    name="enter_last_name",
                    description=f"Enter last name: {last_name}",
                    command=self.agent.type_text(last_name),
                ),
            ])

        if email:
            steps.extend([
                TaskStep(
                    name="find_email",
                    description="Find email field",
                    command=self.agent.find_elements("email input"),
                ),
                TaskStep(
                    name="enter_email",
                    description=f"Enter email: {email}",
                    command=self.agent.type_text(email),
                ),
            ])

        if phone:
            steps.extend([
                TaskStep(
                    name="find_phone",
                    description="Find phone field",
                    command=self.agent.find_elements("phone input"),
                ),
                TaskStep(
                    name="enter_phone",
                    description=f"Enter phone: {phone}",
                    command=self.agent.type_text(phone),
                ),
            ])

        steps.extend([
            TaskStep(
                name="find_save_button",
                description="Find save/create button",
                command=self.agent.find_elements("save button or create button"),
            ),
            TaskStep(
                name="wait_for_save",
                description="Wait for contact to be saved",
                command=self.agent.wait(2.0),
            ),
            TaskStep(
                name="verify_created",
                description="Verify contact was created",
                command=self.agent.screenshot(),
                screenshot_after=True,
            ),
        ])

        return steps

    # =========================================================================
    # Workflow Tasks
    # =========================================================================

    def add_contact_to_workflow_ui(
        self,
        contact_name: str,
        workflow_name: str,
    ) -> list[TaskStep]:
        """Generate steps to add a contact to a workflow via UI.

        Args:
            contact_name: Name of the contact to search for
            workflow_name: Name of the workflow to add them to

        Returns:
            List of TaskSteps
        """
        return [
            TaskStep(
                name="navigate_contacts",
                description="Navigate to contacts page",
                command=self.agent.navigate(f"{self.GHL_BASE_URL}/contacts"),
                wait_after=2.0,
            ),
            TaskStep(
                name="search_contact",
                description=f"Search for contact: {contact_name}",
                command=self.agent.find_elements("search contacts input"),
            ),
            TaskStep(
                name="type_search",
                description="Enter search term",
                command=self.agent.type_text(contact_name),
                wait_after=1.0,
            ),
            TaskStep(
                name="select_contact",
                description="Select the contact from results",
                command=self.agent.find_elements(f"contact row containing {contact_name}"),
            ),
            TaskStep(
                name="find_workflow_action",
                description="Find add to workflow action",
                command=self.agent.find_elements("add to workflow button or workflows menu"),
            ),
            TaskStep(
                name="find_workflow",
                description=f"Find workflow: {workflow_name}",
                command=self.agent.find_elements(f"workflow named {workflow_name}"),
            ),
            TaskStep(
                name="confirm_add",
                description="Confirm adding to workflow",
                command=self.agent.screenshot(),
            ),
        ]

    # =========================================================================
    # Diagnostic Tasks
    # =========================================================================

    def diagnose_page_state(self) -> list[TaskStep]:
        """Generate steps to diagnose current page state.

        Useful for debugging automation issues.

        Returns:
            List of TaskSteps for diagnosis
        """
        return [
            TaskStep(
                name="screenshot_current",
                description="Capture current page state",
                command=self.agent.screenshot(),
            ),
            TaskStep(
                name="read_page_tree",
                description="Read accessibility tree",
                command=self.agent.read_page(filter_type="interactive"),
            ),
            TaskStep(
                name="check_console_errors",
                description="Check for JavaScript errors",
                command=self.agent.get_console_messages(only_errors=True),
            ),
            TaskStep(
                name="check_network_errors",
                description="Check for failed network requests",
                command=self.agent.get_network_requests(limit=20),
            ),
            TaskStep(
                name="get_url",
                description="Get current URL and page info",
                command=self.agent.execute_js("""
                    JSON.stringify({
                        url: window.location.href,
                        title: document.title,
                        readyState: document.readyState,
                        bodyClasses: document.body.className,
                    })
                """),
            ),
        ]
