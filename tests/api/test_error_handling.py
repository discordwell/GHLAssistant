"""Tests for API error handling."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import HTTPStatusError

from tests.conftest import (
    SAMPLE_LOCATION_ID,
    SAMPLE_AGENT_ID,
)


class TestConversationAIErrorHandling:
    """Test error handling for Conversation AI API."""

    @pytest.mark.asyncio
    async def test_list_agents_server_error(self, mock_ghl_client, mock_error_response):
        """Test 500 error raises appropriate exception."""
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_error_response("server_error")
        )

        with pytest.raises(HTTPStatusError) as exc_info:
            await mock_ghl_client.conversation_ai.list_agents()

        assert exc_info.value.response.status_code == 500

    @pytest.mark.asyncio
    async def test_get_agent_not_found(self, mock_ghl_client, mock_error_response):
        """Test 404 error for non-existent agent."""
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_error_response("not_found")
        )

        with pytest.raises(HTTPStatusError) as exc_info:
            await mock_ghl_client.conversation_ai.get_agent("nonexistent_id")

        assert exc_info.value.response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_agent_validation_error(self, mock_ghl_client, mock_error_response):
        """Test 400 error for invalid data."""
        mock_ghl_client._client.post = AsyncMock(
            return_value=mock_error_response("validation")
        )

        with pytest.raises(HTTPStatusError) as exc_info:
            await mock_ghl_client.conversation_ai.create_agent(name="")

        assert exc_info.value.response.status_code == 400

    @pytest.mark.asyncio
    async def test_unauthorized_error(self, mock_ghl_client, mock_error_response):
        """Test 401 error handling."""
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_error_response("unauthorized")
        )

        with pytest.raises(HTTPStatusError) as exc_info:
            await mock_ghl_client.conversation_ai.list_agents()

        assert exc_info.value.response.status_code == 401

    @pytest.mark.asyncio
    async def test_rate_limit_error(self, mock_ghl_client, mock_error_response):
        """Test 429 rate limit handling."""
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_error_response("rate_limit")
        )

        with pytest.raises(HTTPStatusError) as exc_info:
            await mock_ghl_client.conversation_ai.list_agents()

        assert exc_info.value.response.status_code == 429

    @pytest.mark.asyncio
    async def test_delete_agent_not_found(self, mock_ghl_client, mock_error_response):
        """Test 404 error when deleting non-existent agent."""
        mock_ghl_client._client.delete = AsyncMock(
            return_value=mock_error_response("not_found")
        )

        with pytest.raises(HTTPStatusError) as exc_info:
            await mock_ghl_client.conversation_ai.delete_agent("nonexistent_id")

        assert exc_info.value.response.status_code == 404


class TestVoiceAIErrorHandling:
    """Test error handling for Voice AI API."""

    @pytest.mark.asyncio
    async def test_list_agents_server_error(self, mock_ghl_client, mock_error_response):
        """Test 500 error raises appropriate exception."""
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_error_response("server_error")
        )

        with pytest.raises(HTTPStatusError) as exc_info:
            await mock_ghl_client.voice_ai.list_agents()

        assert exc_info.value.response.status_code == 500

    @pytest.mark.asyncio
    async def test_get_agent_not_found(self, mock_ghl_client, mock_error_response):
        """Test 404 error for non-existent agent."""
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_error_response("not_found")
        )

        with pytest.raises(HTTPStatusError) as exc_info:
            await mock_ghl_client.voice_ai.get_agent("nonexistent_id")

        assert exc_info.value.response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_agent_validation_error(self, mock_ghl_client, mock_error_response):
        """Test 400 error for invalid data."""
        mock_ghl_client._client.post = AsyncMock(
            return_value=mock_error_response("validation")
        )

        with pytest.raises(HTTPStatusError) as exc_info:
            await mock_ghl_client.voice_ai.create_agent(name="", voice_id="")

        assert exc_info.value.response.status_code == 400

    @pytest.mark.asyncio
    async def test_unauthorized_error(self, mock_ghl_client, mock_error_response):
        """Test 401 error handling."""
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_error_response("unauthorized")
        )

        with pytest.raises(HTTPStatusError) as exc_info:
            await mock_ghl_client.voice_ai.list_agents()

        assert exc_info.value.response.status_code == 401

    @pytest.mark.asyncio
    async def test_rate_limit_error(self, mock_ghl_client, mock_error_response):
        """Test 429 rate limit handling."""
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_error_response("rate_limit")
        )

        with pytest.raises(HTTPStatusError) as exc_info:
            await mock_ghl_client.voice_ai.list_agents()

        assert exc_info.value.response.status_code == 429

    @pytest.mark.asyncio
    async def test_get_call_not_found(self, mock_ghl_client, mock_error_response):
        """Test 404 error when getting non-existent call."""
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_error_response("not_found")
        )

        with pytest.raises(HTTPStatusError) as exc_info:
            await mock_ghl_client.voice_ai.get_call("nonexistent_id")

        assert exc_info.value.response.status_code == 404
