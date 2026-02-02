"""Chrome MCP Agent - Wrapper for Chrome MCP browser automation.

This module provides a Python interface that mirrors Chrome MCP tool functionality.
It's designed to be used by Claude Code when automating GHL through the browser.

Note: This agent doesn't directly call MCP tools - it provides structured commands
that Claude Code can translate to MCP tool calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ElementRef:
    """Reference to a DOM element from Chrome MCP."""

    ref_id: str
    tag_name: str | None = None
    text: str | None = None
    role: str | None = None
    attributes: dict[str, str] = field(default_factory=dict)

    def __str__(self) -> str:
        parts = [f"ref={self.ref_id}"]
        if self.tag_name:
            parts.append(f"tag={self.tag_name}")
        if self.text:
            text_preview = self.text[:30] + "..." if len(self.text) > 30 else self.text
            parts.append(f"text='{text_preview}'")
        return f"Element({', '.join(parts)})"


@dataclass
class PageState:
    """Current state of the browser page."""

    url: str
    title: str
    tab_id: int
    viewport_width: int = 0
    viewport_height: int = 0

    @property
    def is_ghl(self) -> bool:
        """Check if page is on GHL domain."""
        return "gohighlevel.com" in self.url or "leadconnectorhq.com" in self.url

    @property
    def is_logged_in(self) -> bool:
        """Check if user appears to be logged in (not on login page)."""
        login_indicators = ["/login", "/signin", "/oauth", "/auth"]
        return not any(ind in self.url.lower() for ind in login_indicators)


class ChromeMCPAgent:
    """Chrome MCP Agent wrapper for GHL browser automation.

    This class provides a structured interface for browser automation tasks.
    It's meant to be used by Claude Code to generate appropriate MCP tool calls.

    Usage:
        agent = ChromeMCPAgent(tab_id=123)

        # Find elements
        elements = await agent.find_elements("search bar")

        # Click element
        await agent.click_element(elements[0])

        # Fill form
        await agent.fill_form({
            "email": "user@example.com",
            "password": "secret"
        })

        # Capture network requests
        requests = await agent.get_network_requests("/api/")
    """

    def __init__(self, tab_id: int):
        """Initialize agent with a tab ID.

        Args:
            tab_id: Chrome MCP tab ID from tabs_context_mcp
        """
        self.tab_id = tab_id
        self._page_state: PageState | None = None
        self._elements_cache: dict[str, ElementRef] = {}

    # =========================================================================
    # Page Operations
    # =========================================================================

    def navigate(self, url: str) -> dict[str, Any]:
        """Generate navigate command.

        Returns:
            MCP command dict for mcp__claude-in-chrome__navigate
        """
        return {
            "tool": "mcp__claude-in-chrome__navigate",
            "params": {"url": url, "tabId": self.tab_id},
        }

    def screenshot(self) -> dict[str, Any]:
        """Generate screenshot command.

        Returns:
            MCP command dict for mcp__claude-in-chrome__computer
        """
        return {
            "tool": "mcp__claude-in-chrome__computer",
            "params": {"action": "screenshot", "tabId": self.tab_id},
        }

    def wait(self, seconds: float) -> dict[str, Any]:
        """Generate wait command.

        Returns:
            MCP command dict for mcp__claude-in-chrome__computer
        """
        return {
            "tool": "mcp__claude-in-chrome__computer",
            "params": {"action": "wait", "duration": min(seconds, 30), "tabId": self.tab_id},
        }

    # =========================================================================
    # Element Interaction
    # =========================================================================

    def find_elements(self, query: str) -> dict[str, Any]:
        """Generate find elements command.

        Args:
            query: Natural language description (e.g., "search bar", "login button")

        Returns:
            MCP command dict for mcp__claude-in-chrome__find
        """
        return {
            "tool": "mcp__claude-in-chrome__find",
            "params": {"query": query, "tabId": self.tab_id},
        }

    def read_page(
        self,
        filter_type: str | None = None,
        ref_id: str | None = None,
        depth: int = 15,
    ) -> dict[str, Any]:
        """Generate read page command.

        Args:
            filter_type: "interactive" or "all"
            ref_id: Focus on specific element
            depth: Max tree depth

        Returns:
            MCP command dict for mcp__claude-in-chrome__read_page
        """
        params: dict[str, Any] = {"tabId": self.tab_id, "depth": depth}
        if filter_type:
            params["filter"] = filter_type
        if ref_id:
            params["ref_id"] = ref_id
        return {
            "tool": "mcp__claude-in-chrome__read_page",
            "params": params,
        }

    def click(
        self,
        ref: str | None = None,
        coordinate: tuple[int, int] | None = None,
    ) -> dict[str, Any]:
        """Generate click command.

        Args:
            ref: Element reference ID (e.g., "ref_1")
            coordinate: (x, y) coordinate tuple

        Returns:
            MCP command dict for mcp__claude-in-chrome__computer
        """
        params: dict[str, Any] = {"action": "left_click", "tabId": self.tab_id}
        if ref:
            params["ref"] = ref
        elif coordinate:
            params["coordinate"] = list(coordinate)
        return {
            "tool": "mcp__claude-in-chrome__computer",
            "params": params,
        }

    def double_click(
        self,
        ref: str | None = None,
        coordinate: tuple[int, int] | None = None,
    ) -> dict[str, Any]:
        """Generate double-click command."""
        params: dict[str, Any] = {"action": "double_click", "tabId": self.tab_id}
        if ref:
            params["ref"] = ref
        elif coordinate:
            params["coordinate"] = list(coordinate)
        return {
            "tool": "mcp__claude-in-chrome__computer",
            "params": params,
        }

    def type_text(self, text: str) -> dict[str, Any]:
        """Generate type text command.

        Args:
            text: Text to type

        Returns:
            MCP command dict for mcp__claude-in-chrome__computer
        """
        return {
            "tool": "mcp__claude-in-chrome__computer",
            "params": {"action": "type", "text": text, "tabId": self.tab_id},
        }

    def press_key(self, key: str, repeat: int = 1) -> dict[str, Any]:
        """Generate key press command.

        Args:
            key: Key to press (e.g., "Enter", "Tab", "Escape")
            repeat: Number of times to press

        Returns:
            MCP command dict for mcp__claude-in-chrome__computer
        """
        params: dict[str, Any] = {"action": "key", "text": key, "tabId": self.tab_id}
        if repeat > 1:
            params["repeat"] = repeat
        return {
            "tool": "mcp__claude-in-chrome__computer",
            "params": params,
        }

    def form_input(self, ref: str, value: str | bool | int) -> dict[str, Any]:
        """Generate form input command.

        Args:
            ref: Element reference ID
            value: Value to set

        Returns:
            MCP command dict for mcp__claude-in-chrome__form_input
        """
        return {
            "tool": "mcp__claude-in-chrome__form_input",
            "params": {"ref": ref, "value": value, "tabId": self.tab_id},
        }

    def scroll(
        self,
        direction: str = "down",
        amount: int = 3,
        coordinate: tuple[int, int] | None = None,
    ) -> dict[str, Any]:
        """Generate scroll command.

        Args:
            direction: "up", "down", "left", "right"
            amount: Scroll wheel ticks (1-10)
            coordinate: Position to scroll at

        Returns:
            MCP command dict for mcp__claude-in-chrome__computer
        """
        params: dict[str, Any] = {
            "action": "scroll",
            "scroll_direction": direction,
            "scroll_amount": min(max(amount, 1), 10),
            "tabId": self.tab_id,
        }
        if coordinate:
            params["coordinate"] = list(coordinate)
        return {
            "tool": "mcp__claude-in-chrome__computer",
            "params": params,
        }

    def scroll_to_element(self, ref: str) -> dict[str, Any]:
        """Generate scroll to element command.

        Args:
            ref: Element reference ID

        Returns:
            MCP command dict for mcp__claude-in-chrome__computer
        """
        return {
            "tool": "mcp__claude-in-chrome__computer",
            "params": {"action": "scroll_to", "ref": ref, "tabId": self.tab_id},
        }

    # =========================================================================
    # Network & Console
    # =========================================================================

    def get_network_requests(
        self,
        url_pattern: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Generate network requests command.

        Args:
            url_pattern: Filter by URL pattern
            limit: Max requests to return

        Returns:
            MCP command dict for mcp__claude-in-chrome__read_network_requests
        """
        params: dict[str, Any] = {"tabId": self.tab_id, "limit": limit}
        if url_pattern:
            params["urlPattern"] = url_pattern
        return {
            "tool": "mcp__claude-in-chrome__read_network_requests",
            "params": params,
        }

    def get_console_messages(
        self,
        pattern: str | None = None,
        only_errors: bool = False,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Generate console messages command.

        Args:
            pattern: Regex pattern to filter messages
            only_errors: Only return errors
            limit: Max messages to return

        Returns:
            MCP command dict for mcp__claude-in-chrome__read_console_messages
        """
        params: dict[str, Any] = {"tabId": self.tab_id, "limit": limit}
        if pattern:
            params["pattern"] = pattern
        if only_errors:
            params["onlyErrors"] = True
        return {
            "tool": "mcp__claude-in-chrome__read_console_messages",
            "params": params,
        }

    # =========================================================================
    # JavaScript Execution
    # =========================================================================

    def execute_js(self, code: str) -> dict[str, Any]:
        """Generate JavaScript execution command.

        Args:
            code: JavaScript code to execute

        Returns:
            MCP command dict for mcp__claude-in-chrome__javascript_tool
        """
        return {
            "tool": "mcp__claude-in-chrome__javascript_tool",
            "params": {"action": "javascript_exec", "text": code, "tabId": self.tab_id},
        }

    def get_page_text(self) -> dict[str, Any]:
        """Generate page text extraction command.

        Returns:
            MCP command dict for mcp__claude-in-chrome__get_page_text
        """
        return {
            "tool": "mcp__claude-in-chrome__get_page_text",
            "params": {"tabId": self.tab_id},
        }

    # =========================================================================
    # High-Level Actions (return list of commands)
    # =========================================================================

    def fill_form(self, fields: dict[str, str]) -> list[dict[str, Any]]:
        """Generate commands to fill a form.

        Args:
            fields: Dict mapping field query to value
                    e.g., {"email input": "user@example.com"}

        Returns:
            List of MCP commands to find and fill each field
        """
        commands = []
        for field_query, value in fields.items():
            # First find the element
            commands.append(self.find_elements(field_query))
            # Then we'd need to process the result and fill - this is a hint
            # that the actual filling would happen after finding the ref
        return commands

    def login_sequence(self, email: str, password: str) -> list[dict[str, Any]]:
        """Generate GHL login sequence commands.

        Args:
            email: User email
            password: User password

        Returns:
            List of MCP commands for login flow
        """
        return [
            self.navigate("https://app.gohighlevel.com/login"),
            self.wait(2),
            self.find_elements("email input"),
            # After finding: form_input(ref, email)
            self.find_elements("password input"),
            # After finding: form_input(ref, password)
            self.find_elements("sign in button"),
            # After finding: click(ref)
            self.wait(3),
            self.screenshot(),
        ]


# Helper function to create agent from tab context
def create_agent_from_context(tab_context: dict[str, Any]) -> ChromeMCPAgent | None:
    """Create agent from tabs_context_mcp result.

    Args:
        tab_context: Result from mcp__claude-in-chrome__tabs_context_mcp

    Returns:
        ChromeMCPAgent if valid tab exists, None otherwise
    """
    tabs = tab_context.get("tabs", [])
    if tabs:
        return ChromeMCPAgent(tabs[0].get("id"))
    return None
