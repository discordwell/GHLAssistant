"""Tests for OAuth token storage."""

import json
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from maxlevel.oauth.storage import (
    TokenStorage,
    TokenStorageData,
    OAuthTokenData,
    SessionTokenData,
    OAuthConfig,
)


class TestOAuthTokenData:
    """Tests for OAuthTokenData dataclass."""

    def test_is_expired_false_when_future(self):
        """Token should not be expired when expires_at is in future."""
        future_ts = int(datetime.now().timestamp()) + 3600  # 1 hour from now
        token = OAuthTokenData(
            access_token="test",
            refresh_token="refresh",
            expires_at=future_ts,
        )
        assert token.is_expired is False

    def test_is_expired_true_when_past(self):
        """Token should be expired when expires_at is in past."""
        past_ts = int(datetime.now().timestamp()) - 3600  # 1 hour ago
        token = OAuthTokenData(
            access_token="test",
            refresh_token="refresh",
            expires_at=past_ts,
        )
        assert token.is_expired is True

    def test_is_expired_with_buffer(self):
        """Token should be considered expired within 5-minute buffer."""
        # 4 minutes from now - within buffer, should be considered expired
        near_ts = int(datetime.now().timestamp()) + 240
        token = OAuthTokenData(
            access_token="test",
            refresh_token="refresh",
            expires_at=near_ts,
        )
        assert token.is_expired is True

    def test_expires_in_seconds(self):
        """Should calculate seconds until expiry correctly."""
        future_ts = int(datetime.now().timestamp()) + 3600
        token = OAuthTokenData(
            access_token="test",
            refresh_token="refresh",
            expires_at=future_ts,
        )
        # Should be approximately 3600, allow some tolerance
        assert 3590 <= token.expires_in_seconds <= 3600

    def test_to_dict_and_from_dict(self):
        """Should serialize and deserialize correctly."""
        token = OAuthTokenData(
            access_token="access123",
            refresh_token="refresh456",
            expires_at=1234567890,
            token_type="Bearer",
            scope="contacts.readonly",
            company_id="comp123",
            location_id="loc456",
        )

        data = token.to_dict()
        restored = OAuthTokenData.from_dict(data)

        assert restored.access_token == token.access_token
        assert restored.refresh_token == token.refresh_token
        assert restored.expires_at == token.expires_at
        assert restored.company_id == token.company_id


class TestSessionTokenData:
    """Tests for SessionTokenData dataclass."""

    def test_age_hours(self):
        """Should calculate age correctly."""
        one_hour_ago = int(datetime.now().timestamp()) - 3600
        token = SessionTokenData(
            token="test",
            captured_at=one_hour_ago,
        )
        # Should be approximately 1 hour
        assert 0.9 <= token.age_hours <= 1.1

    def test_to_dict_and_from_dict(self):
        """Should serialize and deserialize correctly."""
        token = SessionTokenData(
            token="session123",
            captured_at=1234567890,
            location_id="loc123",
            company_id="comp456",
            user_id="user789",
        )

        data = token.to_dict()
        restored = SessionTokenData.from_dict(data)

        assert restored.token == token.token
        assert restored.captured_at == token.captured_at
        assert restored.location_id == token.location_id


class TestTokenStorage:
    """Tests for TokenStorage class."""

    @pytest.fixture
    def temp_storage(self, tmp_path):
        """Create a TokenStorage with temporary directory."""
        return TokenStorage(config_dir=tmp_path)

    def test_creates_config_dir(self, tmp_path):
        """Should create config directory if it doesn't exist."""
        new_dir = tmp_path / "new_ghl_config"
        assert not new_dir.exists()

        storage = TokenStorage(config_dir=new_dir)

        assert new_dir.exists()

    def test_load_returns_empty_when_no_file(self, temp_storage):
        """Should return empty TokenStorageData when no file exists."""
        data = temp_storage.load()

        assert data.oauth is None
        assert data.session is None

    def test_save_and_load_oauth(self, temp_storage):
        """Should save and load OAuth tokens correctly."""
        oauth = OAuthTokenData(
            access_token="test_access",
            refresh_token="test_refresh",
            expires_at=int(datetime.now().timestamp()) + 3600,
            company_id="comp123",
        )

        temp_storage.save_oauth_tokens(oauth)
        loaded = temp_storage.load()

        assert loaded.oauth is not None
        assert loaded.oauth.access_token == "test_access"
        assert loaded.oauth.company_id == "comp123"

    def test_save_and_load_session(self, temp_storage):
        """Should save and load session tokens correctly."""
        session = SessionTokenData(
            token="session_token",
            captured_at=int(datetime.now().timestamp()),
            location_id="loc456",
        )

        temp_storage.save_session_token(session)
        loaded = temp_storage.load()

        assert loaded.session is not None
        assert loaded.session.token == "session_token"
        assert loaded.session.location_id == "loc456"

    def test_save_preserves_other_tokens(self, temp_storage):
        """Saving OAuth should preserve session and vice versa."""
        oauth = OAuthTokenData(
            access_token="oauth_token",
            refresh_token="refresh",
            expires_at=int(datetime.now().timestamp()) + 3600,
        )
        session = SessionTokenData(
            token="session_token",
            captured_at=int(datetime.now().timestamp()),
        )

        # Save OAuth first
        temp_storage.save_oauth_tokens(oauth)

        # Save session (should preserve OAuth)
        temp_storage.save_session_token(session)

        loaded = temp_storage.load()
        assert loaded.oauth is not None
        assert loaded.session is not None
        assert loaded.oauth.access_token == "oauth_token"
        assert loaded.session.token == "session_token"

    def test_clear_oauth(self, temp_storage):
        """Should clear only OAuth tokens."""
        oauth = OAuthTokenData(
            access_token="oauth_token",
            refresh_token="refresh",
            expires_at=int(datetime.now().timestamp()) + 3600,
        )
        session = SessionTokenData(
            token="session_token",
            captured_at=int(datetime.now().timestamp()),
        )

        temp_storage.save_oauth_tokens(oauth)
        temp_storage.save_session_token(session)
        temp_storage.clear_oauth()

        loaded = temp_storage.load()
        assert loaded.oauth is None
        assert loaded.session is not None

    def test_clear_session(self, temp_storage):
        """Should clear only session tokens."""
        oauth = OAuthTokenData(
            access_token="oauth_token",
            refresh_token="refresh",
            expires_at=int(datetime.now().timestamp()) + 3600,
        )
        session = SessionTokenData(
            token="session_token",
            captured_at=int(datetime.now().timestamp()),
        )

        temp_storage.save_oauth_tokens(oauth)
        temp_storage.save_session_token(session)
        temp_storage.clear_session()

        loaded = temp_storage.load()
        assert loaded.oauth is not None
        assert loaded.session is None

    def test_clear_all(self, temp_storage):
        """Should clear all tokens."""
        oauth = OAuthTokenData(
            access_token="oauth_token",
            refresh_token="refresh",
            expires_at=int(datetime.now().timestamp()) + 3600,
        )
        session = SessionTokenData(
            token="session_token",
            captured_at=int(datetime.now().timestamp()),
        )

        temp_storage.save_oauth_tokens(oauth)
        temp_storage.save_session_token(session)
        temp_storage.clear_all()

        loaded = temp_storage.load()
        assert loaded.oauth is None
        assert loaded.session is None

    def test_oauth_config_save_and_load(self, temp_storage):
        """Should save and load OAuth config correctly."""
        config = OAuthConfig(
            client_id="client123",
            client_secret="secret456",
            redirect_uri="http://localhost:3000/callback",
            scopes=["contacts.readonly", "contacts.write"],
        )

        temp_storage.save_oauth_config(config)
        loaded = temp_storage.load_oauth_config()

        assert loaded is not None
        assert loaded.client_id == "client123"
        assert loaded.client_secret == "secret456"
        assert "contacts.readonly" in loaded.scopes

    def test_has_oauth_config(self, temp_storage):
        """Should correctly report if OAuth is configured."""
        assert temp_storage.has_oauth_config() is False

        config = OAuthConfig(
            client_id="client123",
            client_secret="secret456",
        )
        temp_storage.save_oauth_config(config)

        assert temp_storage.has_oauth_config() is True

    def test_has_valid_oauth_token(self, temp_storage):
        """Should correctly report if valid OAuth token exists."""
        assert temp_storage.has_valid_oauth_token() is False

        # Expired token
        expired = OAuthTokenData(
            access_token="expired",
            refresh_token="refresh",
            expires_at=int(datetime.now().timestamp()) - 3600,
        )
        temp_storage.save_oauth_tokens(expired)
        assert temp_storage.has_valid_oauth_token() is False

        # Valid token
        valid = OAuthTokenData(
            access_token="valid",
            refresh_token="refresh",
            expires_at=int(datetime.now().timestamp()) + 3600,
        )
        temp_storage.save_oauth_tokens(valid)
        assert temp_storage.has_valid_oauth_token() is True

    def test_get_status(self, temp_storage):
        """Should return comprehensive status."""
        oauth = OAuthTokenData(
            access_token="oauth_token",
            refresh_token="refresh",
            expires_at=int(datetime.now().timestamp()) + 3600,
            company_id="comp123",
        )
        session = SessionTokenData(
            token="session_token",
            captured_at=int(datetime.now().timestamp()),
            location_id="loc456",
        )

        temp_storage.save_oauth_tokens(oauth)
        temp_storage.save_session_token(session)

        status = temp_storage.get_status()

        assert "oauth_token" in status
        assert status["oauth_token"]["valid"] is True
        assert status["oauth_token"]["company_id"] == "comp123"

        assert "session_token" in status
        assert status["session_token"]["location_id"] == "loc456"

    def test_file_permissions(self, temp_storage):
        """Should set restrictive permissions on token files."""
        import os
        import stat

        oauth = OAuthTokenData(
            access_token="secret",
            refresh_token="refresh",
            expires_at=int(datetime.now().timestamp()) + 3600,
        )
        temp_storage.save_oauth_tokens(oauth)

        # Check file permissions (0o600 = owner read/write only)
        mode = os.stat(temp_storage.tokens_file).st_mode
        assert stat.S_IMODE(mode) == 0o600
