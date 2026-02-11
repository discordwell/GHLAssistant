"""Browser automation agent with network capture."""

# Chrome MCP module (no external dependencies)
from .chrome_mcp import ChromeMCPAgent, GHLBrowserTasks
from .ghl_urls import contact_notes_url, contact_tasks_url, extract_location_contact_from_url

__all__ = [
    "ChromeMCPAgent",
    "GHLBrowserTasks",
    "contact_notes_url",
    "contact_tasks_url",
    "extract_location_contact_from_url",
]

# nodriver-based agent (requires nodriver package)
try:
    from .agent import BrowserAgent
    from .network import NetworkCapture
    __all__.extend(["BrowserAgent", "NetworkCapture"])
except ImportError:
    # nodriver not installed - BrowserAgent unavailable
    pass
