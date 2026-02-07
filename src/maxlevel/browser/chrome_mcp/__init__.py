"""Chrome MCP browser automation module for GHL.

This module provides a high-level interface for automating GHL tasks
through Chrome MCP (Claude Code's browser automation protocol).

The ChromeMCPAgent class wraps MCP tool calls and provides GHL-specific
helper methods for common tasks like login, navigation, and token capture.
"""

from .agent import ChromeMCPAgent
from .tasks import GHLBrowserTasks
from .ai_tasks import AIBrowserTasks

__all__ = ["ChromeMCPAgent", "GHLBrowserTasks", "AIBrowserTasks"]
