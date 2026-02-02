"""Browser automation agent with network capture."""

# Chrome MCP module (no external dependencies)
from .chrome_mcp import ChromeMCPAgent, GHLBrowserTasks

__all__ = ["ChromeMCPAgent", "GHLBrowserTasks"]

# nodriver-based agent (requires nodriver package)
try:
    from .agent import BrowserAgent
    from .network import NetworkCapture
    __all__.extend(["BrowserAgent", "NetworkCapture"])
except ImportError:
    # nodriver not installed - BrowserAgent unavailable
    pass
