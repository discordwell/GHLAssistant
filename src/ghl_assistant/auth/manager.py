"""Unified token manager for GHL API access.

Manages both OAuth tokens and session tokens, with automatic
refresh and fallback logic.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ..oauth.storage import TokenStorage, SessionTokenData, OAuthTokenData
from ..oauth.client import OAuthClient, OAuthError


class NoTokenError(Exception):
    """Raised when no valid token is available."""

    def __init__(self, message: str = None):
        default_msg = (
            "No valid authentication token found.\n\n"
            "Options:\n"
            "  1. Run 'ghl oauth connect' for OAuth authentication (recommended)\n"
            "  2. Run 'ghl auth quick' for session-based authentication\n"
            "  3. Run 'ghl auth bridge' to capture token via bookmarklet"
        )
        super().__init__(message or default_msg)


@dataclass
class TokenInfo:
    """Information about the current token."""

    token: str
    source: str  # "oauth" or "session"
    company_id: str | None = None
    location_id: str | None = None
    user_id: str | None = None
    expires_at: int | None = None  # Unix timestamp (OAuth only)
    captured_at: int | None = None  # Unix timestamp (session only)

    @property
    def is_oauth(self) -> bool:
        return self.source == "oauth"

    @property
    def is_session(self) -> bool:
        return self.source == "session"

    @property
    def age_hours(self) -> float | None:
        """Hours since token was issued/captured."""
        if self.captured_at:
            return (datetime.now().timestamp() - self.captured_at) / 3600
        return None


class TokenManager:
    """Unified token manager for OAuth and session tokens.

    Handles:
    - OAuth token management with auto-refresh
    - Session token fallback
    - Token validation
    - ID extraction from tokens

    Usage:
        manager = TokenManager()

        # Get valid token (auto-refreshes OAuth if needed)
        token = await manager.get_token()

        # Get token with metadata
        info = await manager.get_token_info()
        print(f"Using {info.source} token for company {info.company_id}")

        # Check status
        status = manager.get_status()
    """

    def __init__(self, storage: TokenStorage | None = None):
        """Initialize token manager.

        Args:
            storage: TokenStorage instance (uses default if not provided)
        """
        self.storage = storage or TokenStorage()
        self._oauth_client: OAuthClient | None = None

    def _get_oauth_client(self) -> OAuthClient | None:
        """Get OAuth client if configured."""
        if self._oauth_client:
            return self._oauth_client

        try:
            self._oauth_client = OAuthClient.from_config(self.storage)
            return self._oauth_client
        except OAuthError:
            return None

    async def get_token(self) -> str:
        """Get a valid access token.

        Prefers OAuth tokens, falls back to session tokens.
        Auto-refreshes OAuth tokens if expired.

        Returns:
            Valid access token

        Raises:
            NoTokenError: If no valid token available
        """
        info = await self.get_token_info()
        return info.token

    async def get_token_info(self) -> TokenInfo:
        """Get token with metadata.

        Returns:
            TokenInfo with token and metadata

        Raises:
            NoTokenError: If no valid token available
        """
        # Try OAuth first
        oauth_token = await self._get_oauth_token()
        if oauth_token:
            return oauth_token

        # Fall back to session token
        session_token = self._get_session_token()
        if session_token:
            return session_token

        raise NoTokenError()

    async def _get_oauth_token(self) -> TokenInfo | None:
        """Get OAuth token, refreshing if needed."""
        data = self.storage.load()
        if not data.oauth:
            return None

        oauth = data.oauth

        # Check if expired
        if oauth.is_expired:
            # Try to refresh
            refreshed = await self._refresh_oauth_token(oauth)
            if refreshed:
                return refreshed
            return None

        return TokenInfo(
            token=oauth.access_token,
            source="oauth",
            company_id=oauth.company_id,
            location_id=oauth.location_id,
            expires_at=oauth.expires_at,
        )

    async def _refresh_oauth_token(self, oauth: OAuthTokenData) -> TokenInfo | None:
        """Attempt to refresh OAuth token."""
        client = self._get_oauth_client()
        if not client:
            return None

        try:
            tokens = await client.refresh_tokens(oauth.refresh_token)

            # Save new tokens
            self.storage.save_oauth_tokens(tokens.to_storage_data())

            return TokenInfo(
                token=tokens.access_token,
                source="oauth",
                company_id=tokens.company_id,
                location_id=tokens.location_id,
                expires_at=tokens.expires_at,
            )
        except OAuthError as e:
            print(f"Warning: OAuth refresh failed: {e}")
            return None

    def _get_session_token(self) -> TokenInfo | None:
        """Get session token from storage."""
        data = self.storage.load()
        if not data.session or not data.session.token:
            return None

        return TokenInfo(
            token=data.session.token,
            source="session",
            company_id=data.session.company_id,
            location_id=data.session.location_id,
            user_id=data.session.user_id,
            captured_at=data.session.captured_at,
        )

    def has_valid_token(self) -> bool:
        """Check if any valid token is available.

        Note: This doesn't check if OAuth token is expired (would need async).
        Use get_token() for guaranteed valid token.
        """
        data = self.storage.load()

        # Check OAuth (ignoring expiry for sync check)
        if data.oauth and data.oauth.access_token:
            return True

        # Check session
        if data.session and data.session.token:
            return True

        return False

    def get_status(self) -> dict[str, Any]:
        """Get detailed token status."""
        return self.storage.get_status()

    def clear_all(self) -> None:
        """Clear all stored tokens."""
        self.storage.clear_all()

    # Session token management

    def save_session_from_capture(
        self,
        token: str,
        location_id: str | None = None,
        company_id: str | None = None,
        user_id: str | None = None,
        session_file: str | None = None,
    ) -> None:
        """Save a captured session token.

        Args:
            token: The captured access token
            location_id: Location ID from session
            company_id: Company ID from session
            user_id: User ID from session
            session_file: Path to session file for reference
        """
        session_data = SessionTokenData(
            token=token,
            captured_at=int(datetime.now().timestamp()),
            location_id=location_id,
            company_id=company_id,
            user_id=user_id,
            session_file=session_file,
        )
        self.storage.save_session_token(session_data)

    def save_session_from_file(self, filepath: str | Path) -> TokenInfo:
        """Save session token from a captured session file.

        Args:
            filepath: Path to session JSON file

        Returns:
            TokenInfo for the saved token

        Raises:
            ValueError: If no token found in file
        """
        filepath = Path(filepath)

        with open(filepath) as f:
            data = json.load(f)

        token = data.get("auth", {}).get("access_token")
        if not token:
            raise ValueError("No access token found in session file")

        # Extract IDs from API calls
        user_id = None
        company_id = None
        location_id = None

        for call in data.get("api_calls", []):
            url = call.get("url", "")
            if "/users/" in url and not user_id:
                parts = url.split("/users/")
                if len(parts) > 1:
                    uid = parts[1].split("/")[0].split("?")[0]
                    if uid and uid != "identify":
                        user_id = uid
            if "companyId=" in url and not company_id:
                match = re.search(r"companyId=([a-zA-Z0-9]+)", url)
                if match:
                    company_id = match.group(1)
            if "locationId=" in url and not location_id:
                match = re.search(r"locationId=([a-zA-Z0-9]+)", url)
                if match and match.group(1) != "undefined":
                    location_id = match.group(1)

        self.save_session_from_capture(
            token=token,
            location_id=location_id,
            company_id=company_id,
            user_id=user_id,
            session_file=str(filepath),
        )

        return TokenInfo(
            token=token,
            source="session",
            company_id=company_id,
            location_id=location_id,
            user_id=user_id,
            captured_at=int(datetime.now().timestamp()),
        )

    @classmethod
    def from_session_file(cls, filepath: str | Path | None = None) -> "TokenManager":
        """Create manager and load from session file.

        If no filepath provided, uses the most recent session.

        Args:
            filepath: Path to session file (optional)

        Returns:
            TokenManager with session loaded
        """
        manager = cls()

        if filepath is None:
            # Find most recent session
            log_dir = Path(__file__).parent.parent.parent.parent / "data" / "network_logs"
            sessions = sorted(log_dir.glob("session_*.json"))
            if not sessions:
                raise FileNotFoundError(
                    "No session files found. Run 'ghl auth quick' or 'ghl browser capture' first."
                )
            filepath = sessions[-1]

        manager.save_session_from_file(filepath)
        return manager
