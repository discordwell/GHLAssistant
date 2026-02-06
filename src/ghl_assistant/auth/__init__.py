"""Authentication module for GHL Assistant.

Provides unified token management across OAuth and session-based auth.

Usage:
    from ghl_assistant.auth import TokenManager

    # Get a valid token (OAuth preferred, falls back to session)
    manager = TokenManager()
    token = await manager.get_token()

    # Check status
    status = manager.get_status()
"""

from .manager import TokenManager, NoTokenError
from .bridge import TokenBridgeServer

__all__ = [
    "TokenManager",
    "NoTokenError",
    "TokenBridgeServer",
]
