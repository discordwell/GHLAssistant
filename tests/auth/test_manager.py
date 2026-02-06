"""Tests for TokenManager."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from ghl_assistant.auth.manager import TokenManager, TokenInfo, NoTokenError
from ghl_assistant.oauth.storage import (
    TokenStorage,
    OAuthTokenData,
    SessionTokenData,
    OAuthConfig,
)


class TestTokenInfo:
    """Tests for TokenInfo dataclass."""

    def test_is_oauth(self):
        """Should correctly identify OAuth tokens."""
        info = TokenInfo(token="test", source="oauth")
        assert info.is_oauth is True
        assert info.is_session is False

    def test_is_session(self):
        """Should correctly identify session tokens."""
        info = TokenInfo(token="test", source="session")
        assert info.is_session is True
        assert info.is_oauth is False

    def test_age_hours_for_session(self):
        """Should calculate age for session tokens."""
        one_hour_ago = int(datetime.now().timestamp()) - 3600
        info = TokenInfo(
            token="test",
            source="session",
            captured_at=one_hour_ago,
        )
        assert 0.9 <= info.age_hours <= 1.1

    def test_age_hours_none_for_oauth(self):
        """Should return None for OAuth tokens (no captured_at)."""
        info = TokenInfo(
            token="test",
            source="oauth",
            expires_at=int(datetime.now().timestamp()) + 3600,
        )
        assert info.age_hours is None


class TestTokenManager:
    """Tests for TokenManager class."""

    @pytest.fixture
    def temp_storage(self, tmp_path):
        """Create a TokenStorage with temporary directory."""
        return TokenStorage(config_dir=tmp_path)

    @pytest.fixture
    def manager(self, temp_storage):
        """Create a TokenManager with temp storage."""
        return TokenManager(storage=temp_storage)

    def test_has_valid_token_false_when_empty(self, manager):
        """Should return False when no tokens available."""
        assert manager.has_valid_token() is False

    def test_has_valid_token_true_with_oauth(self, manager, temp_storage):
        """Should return True when OAuth token exists."""
        oauth = OAuthTokenData(
            access_token="test",
            refresh_token="refresh",
            expires_at=int(datetime.now().timestamp()) + 3600,
        )
        temp_storage.save_oauth_tokens(oauth)

        assert manager.has_valid_token() is True

    def test_has_valid_token_true_with_session(self, manager, temp_storage):
        """Should return True when session token exists."""
        session = SessionTokenData(
            token="test",
            captured_at=int(datetime.now().timestamp()),
        )
        temp_storage.save_session_token(session)

        assert manager.has_valid_token() is True

    @pytest.mark.asyncio
    async def test_get_token_raises_when_empty(self, manager):
        """Should raise NoTokenError when no tokens available."""
        with pytest.raises(NoTokenError) as exc_info:
            await manager.get_token()

        assert "ghl oauth connect" in str(exc_info.value)
        assert "ghl auth quick" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_token_returns_oauth_when_valid(self, manager, temp_storage):
        """Should return OAuth token when valid."""
        oauth = OAuthTokenData(
            access_token="oauth_access_token",
            refresh_token="refresh",
            expires_at=int(datetime.now().timestamp()) + 3600,
            company_id="comp123",
        )
        temp_storage.save_oauth_tokens(oauth)

        token = await manager.get_token()

        assert token == "oauth_access_token"

    @pytest.mark.asyncio
    async def test_get_token_returns_session_when_no_oauth(self, manager, temp_storage):
        """Should fall back to session token when no OAuth."""
        session = SessionTokenData(
            token="session_token_xyz",
            captured_at=int(datetime.now().timestamp()),
            location_id="loc456",
        )
        temp_storage.save_session_token(session)

        token = await manager.get_token()

        assert token == "session_token_xyz"

    @pytest.mark.asyncio
    async def test_get_token_prefers_oauth(self, manager, temp_storage):
        """Should prefer OAuth over session when both available."""
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

        token = await manager.get_token()

        assert token == "oauth_token"

    @pytest.mark.asyncio
    async def test_get_token_info_includes_metadata(self, manager, temp_storage):
        """Should include metadata in TokenInfo."""
        oauth = OAuthTokenData(
            access_token="oauth_token",
            refresh_token="refresh",
            expires_at=int(datetime.now().timestamp()) + 3600,
            company_id="comp123",
            location_id="loc456",
        )
        temp_storage.save_oauth_tokens(oauth)

        info = await manager.get_token_info()

        assert info.token == "oauth_token"
        assert info.source == "oauth"
        assert info.company_id == "comp123"
        assert info.location_id == "loc456"

    @pytest.mark.asyncio
    async def test_get_token_falls_back_on_expired_oauth(self, manager, temp_storage):
        """Should fall back to session when OAuth expired and refresh fails."""
        # Expired OAuth
        oauth = OAuthTokenData(
            access_token="expired_oauth",
            refresh_token="refresh",
            expires_at=int(datetime.now().timestamp()) - 3600,
        )
        session = SessionTokenData(
            token="session_token",
            captured_at=int(datetime.now().timestamp()),
        )
        temp_storage.save_oauth_tokens(oauth)
        temp_storage.save_session_token(session)

        # No OAuth config, so refresh will fail
        token = await manager.get_token()

        assert token == "session_token"

    @pytest.mark.asyncio
    async def test_oauth_refresh_on_expired(self, manager, temp_storage):
        """Should attempt to refresh expired OAuth token."""
        # Setup expired OAuth with config
        config = OAuthConfig(
            client_id="client123",
            client_secret="secret456",
        )
        temp_storage.save_oauth_config(config)

        oauth = OAuthTokenData(
            access_token="expired_token",
            refresh_token="valid_refresh",
            expires_at=int(datetime.now().timestamp()) - 3600,
        )
        temp_storage.save_oauth_tokens(oauth)

        # Mock the OAuth client's refresh method
        with patch("ghl_assistant.auth.manager.OAuthClient") as MockClient:
            mock_client = MagicMock()
            MockClient.from_config.return_value = mock_client

            # Create mock tokens with to_storage_data method
            mock_tokens = MagicMock()
            mock_tokens.access_token = "refreshed_token"
            mock_tokens.company_id = "comp123"
            mock_tokens.location_id = "loc456"
            mock_tokens.expires_at = int(datetime.now().timestamp()) + 3600
            mock_tokens.to_storage_data.return_value = OAuthTokenData(
                access_token="refreshed_token",
                refresh_token="new_refresh",
                expires_at=int(datetime.now().timestamp()) + 3600,
            )

            mock_client.refresh_tokens = AsyncMock(return_value=mock_tokens)

            token = await manager.get_token()

            assert token == "refreshed_token"
            mock_client.refresh_tokens.assert_called_once_with("valid_refresh")

    def test_save_session_from_capture(self, manager, temp_storage):
        """Should save session token from capture data."""
        manager.save_session_from_capture(
            token="captured_token",
            location_id="loc123",
            company_id="comp456",
            user_id="user789",
        )

        loaded = temp_storage.load()
        assert loaded.session is not None
        assert loaded.session.token == "captured_token"
        assert loaded.session.location_id == "loc123"
        assert loaded.session.company_id == "comp456"

    def test_save_session_from_file(self, manager, tmp_path):
        """Should save session token from session file."""
        # Create a mock session file
        session_file = tmp_path / "session_test.json"
        session_data = {
            "auth": {"access_token": "file_token"},
            "api_calls": [
                {"url": "https://api.example.com/users/user123?foo=bar"},
                {"url": "https://api.example.com/?companyId=comp456"},
                {"url": "https://api.example.com/?locationId=loc789"},
            ],
        }
        session_file.write_text(__import__("json").dumps(session_data))

        info = manager.save_session_from_file(session_file)

        assert info.token == "file_token"
        assert info.source == "session"
        assert info.user_id == "user123"
        assert info.company_id == "comp456"
        assert info.location_id == "loc789"

    def test_save_session_from_file_no_token_raises(self, manager, tmp_path):
        """Should raise ValueError when no token in file."""
        session_file = tmp_path / "bad_session.json"
        session_data = {"auth": {}, "api_calls": []}
        session_file.write_text(__import__("json").dumps(session_data))

        with pytest.raises(ValueError, match="No access token"):
            manager.save_session_from_file(session_file)

    def test_get_status(self, manager, temp_storage):
        """Should return status from storage."""
        oauth = OAuthTokenData(
            access_token="oauth_token",
            refresh_token="refresh",
            expires_at=int(datetime.now().timestamp()) + 3600,
        )
        temp_storage.save_oauth_tokens(oauth)

        status = manager.get_status()

        assert "oauth_token" in status
        assert status["oauth_token"]["valid"] is True

    def test_clear_all(self, manager, temp_storage):
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

        manager.clear_all()

        assert manager.has_valid_token() is False


class TestNoTokenError:
    """Tests for NoTokenError exception."""

    def test_default_message(self):
        """Should have helpful default message."""
        error = NoTokenError()
        message = str(error)

        assert "ghl oauth connect" in message
        assert "ghl auth quick" in message
        assert "ghl auth bridge" in message

    def test_custom_message(self):
        """Should allow custom message."""
        error = NoTokenError("Custom error message")
        assert str(error) == "Custom error message"
