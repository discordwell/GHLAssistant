"""Token storage for OAuth and session tokens.

Stores tokens in ~/.ghl/ directory with restrictive file permissions.

Note: Tokens are stored in plaintext and protected by file permissions (0o600).
For production deployments requiring encryption at rest, consider using
system-level encryption (FileVault, LUKS) or a secrets manager.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any


# Default storage directory
DEFAULT_CONFIG_DIR = Path.home() / ".ghl"


@dataclass
class OAuthTokenData:
    """OAuth token data for storage."""

    access_token: str
    refresh_token: str
    expires_at: int  # Unix timestamp
    token_type: str = "Bearer"
    scope: str = ""
    company_id: str | None = None
    location_id: str | None = None
    user_type: str | None = None  # "Company" or "Location"

    @property
    def is_expired(self) -> bool:
        """Check if access token is expired (with 5 min buffer)."""
        return datetime.now().timestamp() > (self.expires_at - 300)

    @property
    def expires_in_seconds(self) -> int:
        """Seconds until token expires."""
        return max(0, int(self.expires_at - datetime.now().timestamp()))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OAuthTokenData":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class SessionTokenData:
    """Session token data (captured from browser)."""

    token: str
    captured_at: int  # Unix timestamp
    location_id: str | None = None
    company_id: str | None = None
    user_id: str | None = None
    session_file: str | None = None

    @property
    def age_hours(self) -> float:
        """Hours since token was captured."""
        return (datetime.now().timestamp() - self.captured_at) / 3600

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionTokenData":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class TokenStorageData:
    """Complete token storage structure."""

    oauth: OAuthTokenData | None = None
    session: SessionTokenData | None = None
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "oauth": self.oauth.to_dict() if self.oauth else None,
            "session": self.session.to_dict() if self.session else None,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TokenStorageData":
        """Create from dictionary."""
        oauth = OAuthTokenData.from_dict(data["oauth"]) if data.get("oauth") else None
        session = SessionTokenData.from_dict(data["session"]) if data.get("session") else None
        return cls(
            oauth=oauth,
            session=session,
            updated_at=data.get("updated_at", datetime.now().isoformat()),
        )


@dataclass
class OAuthConfig:
    """OAuth client configuration."""

    client_id: str
    client_secret: str
    redirect_uri: str = "http://localhost:3000/callback"
    scopes: list[str] = field(default_factory=list)
    marketplace_app_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OAuthConfig":
        """Create from dictionary."""
        return cls(**data)


class TokenStorage:
    """Secure storage for OAuth and session tokens.

    Stores tokens in ~/.ghl/tokens.json with optional encryption.

    Usage:
        storage = TokenStorage()

        # Save OAuth tokens
        storage.save_oauth_tokens(oauth_data)

        # Save session token
        storage.save_session_token(session_data)

        # Load tokens
        data = storage.load()
        if data.oauth and not data.oauth.is_expired:
            token = data.oauth.access_token
    """

    def __init__(
        self,
        config_dir: Path | str | None = None,
        encrypt: bool = False,
        encryption_key: str | None = None,
    ):
        """Initialize token storage.

        Args:
            config_dir: Directory for config files (default: ~/.ghl)
            encrypt: Whether to encrypt stored tokens
            encryption_key: Key for encryption (if not provided, uses machine-specific key)
        """
        self.config_dir = Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.tokens_file = self.config_dir / "tokens.json"
        self.oauth_config_file = self.config_dir / "oauth_config.json"

        self.encrypt = encrypt
        self._encryption_key = encryption_key

    def _encrypt(self, data: str) -> str:
        """Placeholder for encryption - tokens protected by file permissions only.

        Note: Token encryption is not implemented. Tokens are stored in plaintext
        and protected by restrictive file permissions (0o600). For production
        deployments requiring encryption at rest, consider using system-level
        encryption (FileVault, LUKS) or a secrets manager.
        """
        # Encryption disabled - rely on file permissions for security
        return data

    def _decrypt(self, data: str) -> str:
        """Placeholder for decryption - tokens stored in plaintext."""
        return data

    def load(self) -> TokenStorageData:
        """Load token data from storage."""
        if not self.tokens_file.exists():
            return TokenStorageData()

        try:
            with open(self.tokens_file) as f:
                content = f.read()

            if self.encrypt:
                content = self._decrypt(content)

            data = json.loads(content)
            return TokenStorageData.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"Warning: Could not load tokens: {e}")
            return TokenStorageData()

    def save(self, data: TokenStorageData) -> None:
        """Save token data to storage."""
        data.updated_at = datetime.now().isoformat()
        content = json.dumps(data.to_dict(), indent=2)

        if self.encrypt:
            content = self._encrypt(content)

        with open(self.tokens_file, "w") as f:
            f.write(content)

        # Set restrictive permissions
        os.chmod(self.tokens_file, 0o600)

    def save_oauth_tokens(self, oauth_data: OAuthTokenData) -> None:
        """Save OAuth tokens, preserving session token."""
        data = self.load()
        data.oauth = oauth_data
        self.save(data)

    def save_session_token(self, session_data: SessionTokenData) -> None:
        """Save session token, preserving OAuth tokens."""
        data = self.load()
        data.session = session_data
        self.save(data)

    def clear_oauth(self) -> None:
        """Clear OAuth tokens."""
        data = self.load()
        data.oauth = None
        self.save(data)

    def clear_session(self) -> None:
        """Clear session token."""
        data = self.load()
        data.session = None
        self.save(data)

    def clear_all(self) -> None:
        """Clear all tokens."""
        self.save(TokenStorageData())

    # OAuth config methods

    def load_oauth_config(self) -> OAuthConfig | None:
        """Load OAuth client configuration."""
        if not self.oauth_config_file.exists():
            return None

        try:
            with open(self.oauth_config_file) as f:
                data = json.load(f)
            return OAuthConfig.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    def save_oauth_config(self, config: OAuthConfig) -> None:
        """Save OAuth client configuration."""
        with open(self.oauth_config_file, "w") as f:
            json.dump(config.to_dict(), f, indent=2)

        # Set restrictive permissions (contains client_secret)
        os.chmod(self.oauth_config_file, 0o600)

    def has_oauth_config(self) -> bool:
        """Check if OAuth is configured."""
        return self.oauth_config_file.exists()

    def has_valid_oauth_token(self) -> bool:
        """Check if there's a valid (non-expired) OAuth token."""
        data = self.load()
        return data.oauth is not None and not data.oauth.is_expired

    def has_session_token(self) -> bool:
        """Check if there's a session token."""
        data = self.load()
        return data.session is not None and data.session.token is not None

    def get_status(self) -> dict[str, Any]:
        """Get token status summary."""
        data = self.load()
        oauth_config = self.load_oauth_config()

        status = {
            "config_dir": str(self.config_dir),
            "oauth_configured": oauth_config is not None,
            "oauth_token": None,
            "session_token": None,
        }

        if data.oauth:
            status["oauth_token"] = {
                "valid": not data.oauth.is_expired,
                "expires_in_seconds": data.oauth.expires_in_seconds,
                "company_id": data.oauth.company_id,
                "location_id": data.oauth.location_id,
                "scope": data.oauth.scope,
            }

        if data.session:
            status["session_token"] = {
                "age_hours": round(data.session.age_hours, 1),
                "location_id": data.session.location_id,
                "company_id": data.session.company_id,
                "user_id": data.session.user_id,
            }

        return status
