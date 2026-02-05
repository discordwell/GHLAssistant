"""OAuth module for GHL Marketplace App authentication.

Provides OAuth 2.0 Authorization Code flow for GHL Private Marketplace Apps.
This is the recommended method for production agency automation.

Usage:
    from ghl_assistant.oauth import OAuthClient, TokenStorage

    # Setup OAuth client
    client = OAuthClient.from_config()

    # Start OAuth flow
    auth_url = client.get_authorization_url()
    # User visits auth_url and grants permission

    # Exchange code for tokens
    tokens = await client.exchange_code(auth_code)

    # Use tokens
    access_token = tokens.access_token  # Valid for 24 hours
    refresh_token = tokens.refresh_token  # Valid for 1 year

    # Auto-refresh when expired
    if tokens.is_expired:
        tokens = await client.refresh_tokens(tokens.refresh_token)
"""

from .client import OAuthClient, OAuthTokens, OAuthError, validate_token
from .storage import TokenStorage, OAuthConfig, OAuthTokenData, SessionTokenData
from .server import OAuthCallbackServer, run_oauth_flow

__all__ = [
    "OAuthClient",
    "OAuthTokens",
    "OAuthError",
    "TokenStorage",
    "OAuthConfig",
    "OAuthTokenData",
    "SessionTokenData",
    "OAuthCallbackServer",
    "run_oauth_flow",
    "validate_token",
]
