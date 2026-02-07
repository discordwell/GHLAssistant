"""Tests for OAuth client."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from maxlevel.oauth.client import (
    OAuthClient,
    OAuthTokens,
    OAuthError,
    validate_token,
    GHL_AUTH_URL,
    GHL_TOKEN_URL,
)
from maxlevel.oauth.storage import TokenStorage, OAuthConfig


class TestOAuthTokens:
    """Tests for OAuthTokens dataclass."""

    def test_expires_at(self):
        """Should calculate expires_at correctly."""
        tokens = OAuthTokens(
            access_token="test",
            refresh_token="refresh",
            expires_in=3600,  # 1 hour
        )

        now = int(datetime.now().timestamp())
        # Should be approximately now + 3600
        assert now + 3590 <= tokens.expires_at <= now + 3610

    def test_to_storage_data(self):
        """Should convert to storage format correctly."""
        tokens = OAuthTokens(
            access_token="access123",
            refresh_token="refresh456",
            expires_in=7200,
            scope="contacts.readonly",
            company_id="comp123",
            location_id="loc456",
        )

        storage_data = tokens.to_storage_data()

        assert storage_data.access_token == "access123"
        assert storage_data.refresh_token == "refresh456"
        assert storage_data.scope == "contacts.readonly"
        assert storage_data.company_id == "comp123"


class TestOAuthClient:
    """Tests for OAuthClient class."""

    @pytest.fixture
    def client(self):
        """Create a basic OAuth client."""
        return OAuthClient(
            client_id="test_client_id",
            client_secret="test_client_secret",
            redirect_uri="http://localhost:3000/callback",
            scopes=["contacts.readonly", "contacts.write"],
        )

    @pytest.fixture
    def temp_storage(self, tmp_path):
        """Create a TokenStorage with temporary directory."""
        return TokenStorage(config_dir=tmp_path)

    def test_generate_state(self, client):
        """Should generate unique state values."""
        state1 = client.generate_state()
        state2 = client.generate_state()

        assert state1 is not None
        assert len(state1) > 20
        # Note: generate_state replaces _state, so state2 will be different
        assert state2 is not None

    def test_get_authorization_url(self, client):
        """Should generate correct authorization URL."""
        state = client.generate_state()
        url = client.get_authorization_url(state=state)

        assert GHL_AUTH_URL in url
        assert "client_id=test_client_id" in url
        assert "redirect_uri=http" in url
        assert f"state={state}" in url
        assert "response_type=code" in url
        assert "scope=contacts.readonly" in url

    def test_get_authorization_url_generates_state(self, client):
        """Should auto-generate state if not provided."""
        url = client.get_authorization_url()

        assert "state=" in url
        assert client._state is not None

    def test_verify_state_true_on_match(self, client):
        """Should return True when state matches."""
        state = client.generate_state()

        assert client.verify_state(state) is True

    def test_verify_state_false_on_mismatch(self, client):
        """Should return False when state doesn't match."""
        client.generate_state()

        assert client.verify_state("wrong_state") is False

    def test_verify_state_false_when_no_state(self, client):
        """Should return False when no state was generated."""
        assert client.verify_state("any_state") is False

    def test_from_config(self, temp_storage):
        """Should create client from stored config."""
        config = OAuthConfig(
            client_id="stored_client_id",
            client_secret="stored_secret",
            redirect_uri="http://localhost:4000/callback",
            scopes=["workflows.readonly"],
        )
        temp_storage.save_oauth_config(config)

        client = OAuthClient.from_config(temp_storage)

        assert client.client_id == "stored_client_id"
        assert client.client_secret == "stored_secret"
        assert client.redirect_uri == "http://localhost:4000/callback"
        assert "workflows.readonly" in client.scopes

    def test_from_config_raises_when_not_configured(self, temp_storage):
        """Should raise OAuthError when no config exists."""
        with pytest.raises(OAuthError) as exc_info:
            OAuthClient.from_config(temp_storage)

        assert exc_info.value.error_code == "not_configured"
        assert "maxlevel oauth setup" in str(exc_info.value)

    def test_from_credentials_saves_config(self, temp_storage):
        """Should save config when save=True."""
        client = OAuthClient.from_credentials(
            client_id="new_client",
            client_secret="new_secret",
            scopes=["contacts.readonly"],
            save=True,
            storage=temp_storage,
        )

        assert client.client_id == "new_client"

        # Verify config was saved
        loaded = temp_storage.load_oauth_config()
        assert loaded is not None
        assert loaded.client_id == "new_client"

    @pytest.mark.asyncio
    async def test_exchange_code_success(self, client):
        """Should exchange code for tokens successfully."""
        client.generate_state()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 86400,
            "token_type": "Bearer",
            "scope": "contacts.readonly",
            "companyId": "comp123",
            "locationId": "loc456",
        }

        with patch("httpx.AsyncClient") as MockAsyncClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockAsyncClient.return_value = mock_client

            tokens = await client.exchange_code(
                code="auth_code_123",
                state=client._state,
            )

            assert tokens.access_token == "new_access_token"
            assert tokens.refresh_token == "new_refresh_token"
            assert tokens.company_id == "comp123"

    @pytest.mark.asyncio
    async def test_exchange_code_state_mismatch(self, client):
        """Should raise OAuthError on state mismatch."""
        client.generate_state()

        with pytest.raises(OAuthError) as exc_info:
            await client.exchange_code(
                code="auth_code",
                state="wrong_state",
                verify_state=True,
            )

        assert exc_info.value.error_code == "state_mismatch"
        assert "CSRF" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_exchange_code_skip_state_verification(self, client):
        """Should skip state verification when disabled."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "token",
            "refresh_token": "refresh",
            "expires_in": 86400,
        }

        with patch("httpx.AsyncClient") as MockAsyncClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockAsyncClient.return_value = mock_client

            # Should not raise even with wrong state
            tokens = await client.exchange_code(
                code="auth_code",
                state="wrong_state",
                verify_state=False,
            )

            assert tokens.access_token == "token"

    @pytest.mark.asyncio
    async def test_exchange_code_failure(self, client):
        """Should raise OAuthError on exchange failure."""
        client.generate_state()

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.content = b'{"error": "invalid_grant"}'
        mock_response.json.return_value = {"error": "invalid_grant", "error_description": "Code expired"}

        with patch("httpx.AsyncClient") as MockAsyncClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockAsyncClient.return_value = mock_client

            with pytest.raises(OAuthError) as exc_info:
                await client.exchange_code(
                    code="expired_code",
                    state=client._state,
                )

            assert exc_info.value.error_code == "invalid_grant"

    @pytest.mark.asyncio
    async def test_refresh_tokens_success(self, client):
        """Should refresh tokens successfully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "refreshed_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 86400,
            "token_type": "Bearer",
        }

        with patch("httpx.AsyncClient") as MockAsyncClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockAsyncClient.return_value = mock_client

            tokens = await client.refresh_tokens("old_refresh_token")

            assert tokens.access_token == "refreshed_access_token"
            assert tokens.refresh_token == "new_refresh_token"

    @pytest.mark.asyncio
    async def test_refresh_tokens_failure(self, client):
        """Should raise OAuthError on refresh failure."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.content = b'{"error": "invalid_grant"}'
        mock_response.json.return_value = {"error": "invalid_grant"}

        with patch("httpx.AsyncClient") as MockAsyncClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockAsyncClient.return_value = mock_client

            with pytest.raises(OAuthError) as exc_info:
                await client.refresh_tokens("invalid_refresh")

            assert "refresh_failed" in exc_info.value.error_code or "invalid_grant" in exc_info.value.error_code


class TestValidateToken:
    """Tests for the validate_token utility function."""

    @pytest.mark.asyncio
    async def test_valid_token(self):
        """Should return valid=True for working token."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "user123", "email": "test@example.com"}

        with patch("httpx.AsyncClient") as MockAsyncClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockAsyncClient.return_value = mock_client

            result = await validate_token("valid_token")

            assert result["valid"] is True
            assert "user" in result

    @pytest.mark.asyncio
    async def test_invalid_token(self):
        """Should return valid=False for invalid token."""
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("httpx.AsyncClient") as MockAsyncClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockAsyncClient.return_value = mock_client

            result = await validate_token("invalid_token")

            assert result["valid"] is False
            assert "error" in result


class TestOAuthError:
    """Tests for OAuthError exception."""

    def test_basic_error(self):
        """Should store basic error info."""
        error = OAuthError("Something went wrong")

        assert str(error) == "Something went wrong"
        assert error.error_code is None
        assert error.details == {}

    def test_error_with_code_and_details(self):
        """Should store error code and details."""
        error = OAuthError(
            "Token exchange failed",
            error_code="invalid_grant",
            details={"error_description": "Code expired"},
        )

        assert error.error_code == "invalid_grant"
        assert "error_description" in error.details
