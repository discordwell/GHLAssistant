"""OAuth 2.0 client for GHL Marketplace Apps.

Handles the OAuth Authorization Code flow:
1. Generate authorization URL
2. Handle callback with authorization code
3. Exchange code for access + refresh tokens
4. Refresh tokens when expired
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

import httpx

from .storage import TokenStorage, OAuthConfig, OAuthTokenData


# GHL OAuth endpoints
GHL_AUTH_URL = "https://marketplace.leadconnectorhq.com/oauth/chooselocation"
GHL_TOKEN_URL = "https://services.leadconnectorhq.com/oauth/token"


@dataclass
class OAuthTokens:
    """OAuth tokens returned from GHL."""

    access_token: str
    refresh_token: str
    expires_in: int  # seconds
    token_type: str = "Bearer"
    scope: str = ""
    user_type: str | None = None  # "Company" or "Location"
    company_id: str | None = None
    location_id: str | None = None
    _created_at: int = field(default_factory=lambda: int(datetime.now().timestamp()))

    @property
    def expires_at(self) -> int:
        """Unix timestamp when token expires (based on creation time)."""
        return self._created_at + self.expires_in

    def to_storage_data(self) -> OAuthTokenData:
        """Convert to storage format."""
        return OAuthTokenData(
            access_token=self.access_token,
            refresh_token=self.refresh_token,
            expires_at=self.expires_at,
            token_type=self.token_type,
            scope=self.scope,
            company_id=self.company_id,
            location_id=self.location_id,
            user_type=self.user_type,
        )


class OAuthError(Exception):
    """OAuth-related error."""

    def __init__(self, message: str, error_code: str | None = None, details: dict | None = None):
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}


class OAuthClient:
    """OAuth 2.0 client for GHL Marketplace Apps.

    Usage:
        # Setup
        client = OAuthClient(
            client_id="your_client_id",
            client_secret="your_client_secret",
            redirect_uri="http://localhost:3000/callback",
        )

        # Generate auth URL for user
        state = client.generate_state()
        auth_url = client.get_authorization_url(state=state)

        # User visits auth_url and grants permission
        # GHL redirects to redirect_uri with ?code=xxx&state=xxx

        # Exchange code for tokens
        tokens = await client.exchange_code(code, state)

        # Later, refresh when expired
        new_tokens = await client.refresh_tokens(tokens.refresh_token)
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str = "http://localhost:3000/callback",
        scopes: list[str] | None = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scopes = scopes or []

        self._state: str | None = None

    @classmethod
    def from_config(cls, storage: TokenStorage | None = None) -> "OAuthClient":
        """Create client from stored configuration.

        Args:
            storage: TokenStorage instance (uses default if not provided)

        Raises:
            OAuthError: If no configuration found
        """
        storage = storage or TokenStorage()
        config = storage.load_oauth_config()

        if not config:
            raise OAuthError(
                "OAuth not configured. Run 'ghl oauth setup' first.",
                error_code="not_configured",
            )

        return cls(
            client_id=config.client_id,
            client_secret=config.client_secret,
            redirect_uri=config.redirect_uri,
            scopes=config.scopes,
        )

    @classmethod
    def from_credentials(
        cls,
        client_id: str,
        client_secret: str,
        redirect_uri: str = "http://localhost:3000/callback",
        scopes: list[str] | None = None,
        save: bool = True,
        storage: TokenStorage | None = None,
    ) -> "OAuthClient":
        """Create client from credentials, optionally saving to storage.

        Args:
            client_id: OAuth client ID from GHL Marketplace
            client_secret: OAuth client secret
            redirect_uri: Callback URL (must match Marketplace config)
            scopes: List of OAuth scopes
            save: Whether to save config to storage
            storage: TokenStorage instance
        """
        client = cls(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scopes=scopes or [],
        )

        if save:
            storage = storage or TokenStorage()
            config = OAuthConfig(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                scopes=scopes or [],
            )
            storage.save_oauth_config(config)

        return client

    def generate_state(self) -> str:
        """Generate a random state value for CSRF protection."""
        self._state = secrets.token_urlsafe(32)
        return self._state

    def get_authorization_url(
        self,
        state: str | None = None,
        scopes: list[str] | None = None,
    ) -> str:
        """Generate the authorization URL for user consent.

        Args:
            state: CSRF protection token (generates if not provided)
            scopes: Override default scopes

        Returns:
            URL to redirect user to for OAuth consent
        """
        if state:
            self._state = state
        elif not self._state:
            self._state = self.generate_state()

        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "state": self._state,
        }

        scope_list = scopes or self.scopes
        if scope_list:
            params["scope"] = " ".join(scope_list)

        return f"{GHL_AUTH_URL}?{urlencode(params)}"

    def verify_state(self, state: str) -> bool:
        """Verify the state parameter from callback matches."""
        if not self._state:
            return False
        return secrets.compare_digest(self._state, state)

    async def exchange_code(
        self,
        code: str,
        state: str | None = None,
        verify_state: bool = True,
    ) -> OAuthTokens:
        """Exchange authorization code for access tokens.

        Args:
            code: Authorization code from callback
            state: State parameter from callback (for verification)
            verify_state: Whether to verify state matches

        Returns:
            OAuthTokens with access and refresh tokens

        Raises:
            OAuthError: If exchange fails or state doesn't match
        """
        if verify_state and state:
            if not self.verify_state(state):
                raise OAuthError(
                    "State mismatch - possible CSRF attack",
                    error_code="state_mismatch",
                )

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                GHL_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if response.status_code != 200:
                try:
                    error_data = response.json() if response.content else {}
                except Exception:
                    error_data = {"raw_response": response.text[:500]}
                raise OAuthError(
                    f"Token exchange failed: {response.status_code}",
                    error_code=error_data.get("error", "exchange_failed"),
                    details=error_data,
                )

            data = response.json()
            return self._parse_token_response(data)

    async def refresh_tokens(self, refresh_token: str) -> OAuthTokens:
        """Refresh access token using refresh token.

        Args:
            refresh_token: Valid refresh token

        Returns:
            New OAuthTokens with fresh access token

        Raises:
            OAuthError: If refresh fails
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                GHL_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if response.status_code != 200:
                try:
                    error_data = response.json() if response.content else {}
                except Exception:
                    error_data = {"raw_response": response.text[:500]}
                raise OAuthError(
                    f"Token refresh failed: {response.status_code}",
                    error_code=error_data.get("error", "refresh_failed"),
                    details=error_data,
                )

            data = response.json()
            return self._parse_token_response(data)

    def _parse_token_response(self, data: dict[str, Any]) -> OAuthTokens:
        """Parse token response from GHL.

        Raises:
            OAuthError: If required fields are missing
        """
        try:
            return OAuthTokens(
                access_token=data["access_token"],
                refresh_token=data["refresh_token"],
                expires_in=data.get("expires_in", 86400),  # Default 24 hours
                token_type=data.get("token_type", "Bearer"),
                scope=data.get("scope", ""),
                user_type=data.get("userType"),
                company_id=data.get("companyId"),
                location_id=data.get("locationId"),
            )
        except KeyError as e:
            raise OAuthError(
                f"Invalid token response: missing {e}",
                error_code="invalid_response",
                details={"missing_field": str(e), "response_keys": list(data.keys())},
            )

    async def revoke_token(self, token: str) -> bool:
        """Revoke an access or refresh token.

        Note: GHL may not support token revocation via API.
        This is provided for completeness.

        Args:
            token: Token to revoke

        Returns:
            True if successful
        """
        # GHL doesn't have a standard revoke endpoint
        # The token will expire naturally
        # For now, just return True
        return True


async def validate_token(access_token: str) -> dict[str, Any]:
    """Test if an access token is valid by making a simple API call.

    Args:
        access_token: Token to test

    Returns:
        Dict with 'valid' bool and user info if valid
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            "https://services.leadconnectorhq.com/users/",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Version": "2021-07-28",
            },
        )

        if response.status_code == 200:
            data = response.json()
            return {
                "valid": True,
                "user": data,
            }
        elif response.status_code == 401:
            return {
                "valid": False,
                "error": "Token expired or invalid",
            }
        else:
            return {
                "valid": False,
                "error": f"Unexpected status: {response.status_code}",
            }


# Alias for backward compatibility
test_token = validate_token
