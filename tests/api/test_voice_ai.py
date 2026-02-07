"""Tests for Voice AI API module."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from maxlevel.api.voice_ai import VoiceAIAPI
from tests.conftest import (
    SAMPLE_LOCATION_ID,
    SAMPLE_AGENT_ID,
    SAMPLE_ACTION_ID,
    SAMPLE_WORKFLOW_ID,
    SAMPLE_CONTACT_ID,
    SAMPLE_CALL_ID,
    SAMPLE_VOICE_ID,
    SAMPLE_PHONE_ID,
    MOCK_VOICE_AI_AGENT,
    MOCK_ACTION,
    MOCK_CALL,
    MOCK_VOICE,
    MOCK_PHONE_NUMBER,
    MOCK_SETTINGS,
)


class TestVoiceAIAPI:
    """Test suite for VoiceAIAPI class."""

    # =========================================================================
    # Voice Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_list_voices(self, mock_ghl_client, mock_response):
        """Test listing available voices."""
        expected_data = {"voices": [MOCK_VOICE]}
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.voice_ai.list_voices()

        assert result == expected_data
        call_args = mock_ghl_client._client.get.call_args
        assert "voice-ai/voices" in call_args[0][0]
        assert call_args[1]["params"]["locationId"] == SAMPLE_LOCATION_ID

    # =========================================================================
    # Agent Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_list_agents(self, mock_ghl_client, mock_response):
        """Test listing voice AI agents."""
        expected_data = {"agents": [MOCK_VOICE_AI_AGENT], "total": 1}
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.voice_ai.list_agents()

        assert result == expected_data
        mock_ghl_client._client.get.assert_called_once()
        call_args = mock_ghl_client._client.get.call_args
        assert "voice-ai/agents" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_list_agents_with_pagination(self, mock_ghl_client, mock_response):
        """Test listing agents with pagination."""
        expected_data = {"agents": [], "total": 0}
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(expected_data)
        )

        await mock_ghl_client.voice_ai.list_agents(limit=10, skip=5)

        call_args = mock_ghl_client._client.get.call_args
        assert call_args[1]["params"]["limit"] == 10
        assert call_args[1]["params"]["skip"] == 5

    @pytest.mark.asyncio
    async def test_get_agent(self, mock_ghl_client, mock_response):
        """Test getting a single voice agent."""
        expected_data = {"agent": MOCK_VOICE_AI_AGENT}
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.voice_ai.get_agent(SAMPLE_AGENT_ID)

        assert result == expected_data
        assert SAMPLE_AGENT_ID in mock_ghl_client._client.get.call_args[0][0]

    @pytest.mark.asyncio
    async def test_create_agent_minimal(self, mock_ghl_client, mock_response):
        """Test creating a voice agent with minimal parameters."""
        expected_data = {"agent": MOCK_VOICE_AI_AGENT}
        mock_ghl_client._client.post = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.voice_ai.create_agent(
            name="Voice Bot",
            voice_id=SAMPLE_VOICE_ID,
        )

        assert result == expected_data
        call_args = mock_ghl_client._client.post.call_args
        json_data = call_args[1]["json"]
        assert json_data["name"] == "Voice Bot"
        assert json_data["voiceId"] == SAMPLE_VOICE_ID
        assert json_data["model"] == "gpt-4"  # Default
        assert json_data["temperature"] == 0.7  # Default

    @pytest.mark.asyncio
    async def test_create_agent_full(self, mock_ghl_client, mock_response):
        """Test creating a voice agent with all parameters."""
        expected_data = {"agent": MOCK_VOICE_AI_AGENT}
        mock_ghl_client._client.post = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.voice_ai.create_agent(
            name="Full Voice Bot",
            voice_id=SAMPLE_VOICE_ID,
            prompt="You are a receptionist.",
            phone_number_id=SAMPLE_PHONE_ID,
            greeting="Hello! How can I help you?",
            model="gpt-3.5-turbo",
            temperature=0.5,
        )

        assert result == expected_data
        call_args = mock_ghl_client._client.post.call_args
        json_data = call_args[1]["json"]
        assert json_data["name"] == "Full Voice Bot"
        assert json_data["voiceId"] == SAMPLE_VOICE_ID
        assert json_data["prompt"] == "You are a receptionist."
        assert json_data["phoneNumberId"] == SAMPLE_PHONE_ID
        assert json_data["greeting"] == "Hello! How can I help you?"
        assert json_data["model"] == "gpt-3.5-turbo"
        assert json_data["temperature"] == 0.5

    @pytest.mark.asyncio
    async def test_update_agent_uses_patch(self, mock_ghl_client, mock_response):
        """Test that update_agent uses PATCH method (not PUT)."""
        expected_data = {"agent": MOCK_VOICE_AI_AGENT}
        mock_ghl_client._client.patch = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.voice_ai.update_agent(
            SAMPLE_AGENT_ID,
            name="Updated Voice Bot",
            enabled=False,
        )

        assert result == expected_data
        # Verify PATCH was called, not PUT
        mock_ghl_client._client.patch.assert_called_once()
        mock_ghl_client._client.put.assert_not_called()

        call_args = mock_ghl_client._client.patch.call_args
        assert SAMPLE_AGENT_ID in call_args[0][0]
        assert call_args[1]["json"]["name"] == "Updated Voice Bot"
        assert call_args[1]["json"]["enabled"] is False

    @pytest.mark.asyncio
    async def test_update_agent_partial(self, mock_ghl_client, mock_response):
        """Test updating only specific fields."""
        expected_data = {"agent": MOCK_VOICE_AI_AGENT}
        mock_ghl_client._client.patch = AsyncMock(
            return_value=mock_response(expected_data)
        )

        await mock_ghl_client.voice_ai.update_agent(
            SAMPLE_AGENT_ID,
            voice_id="new_voice_id",
        )

        call_args = mock_ghl_client._client.patch.call_args
        json_data = call_args[1]["json"]
        assert json_data["voiceId"] == "new_voice_id"
        assert "name" not in json_data
        assert "prompt" not in json_data

    @pytest.mark.asyncio
    async def test_delete_agent(self, mock_ghl_client, mock_response):
        """Test deleting a voice agent."""
        expected_data = {"succeeded": True}
        mock_ghl_client._client.delete = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.voice_ai.delete_agent(SAMPLE_AGENT_ID)

        assert result == expected_data
        assert SAMPLE_AGENT_ID in mock_ghl_client._client.delete.call_args[0][0]

    # =========================================================================
    # Action Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_list_actions(self, mock_ghl_client, mock_response):
        """Test listing voice agent actions."""
        expected_data = {"actions": [MOCK_ACTION]}
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.voice_ai.list_actions(SAMPLE_AGENT_ID)

        assert result == expected_data
        call_url = mock_ghl_client._client.get.call_args[0][0]
        assert SAMPLE_AGENT_ID in call_url
        assert "actions" in call_url

    @pytest.mark.asyncio
    async def test_create_action_workflow(self, mock_ghl_client, mock_response):
        """Test creating a workflow action."""
        expected_data = {"action": MOCK_ACTION}
        mock_ghl_client._client.post = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.voice_ai.create_action(
            SAMPLE_AGENT_ID,
            action_type="workflow",
            name="Book Appointment",
            trigger_condition="intent:schedule",
            workflow_id=SAMPLE_WORKFLOW_ID,
        )

        assert result == expected_data
        call_args = mock_ghl_client._client.post.call_args
        json_data = call_args[1]["json"]
        assert json_data["type"] == "workflow"
        assert json_data["name"] == "Book Appointment"
        assert json_data["triggerCondition"] == "intent:schedule"
        assert json_data["workflowId"] == SAMPLE_WORKFLOW_ID

    @pytest.mark.asyncio
    async def test_create_action_webhook(self, mock_ghl_client, mock_response):
        """Test creating a webhook action."""
        expected_data = {"action": MOCK_ACTION}
        mock_ghl_client._client.post = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.voice_ai.create_action(
            SAMPLE_AGENT_ID,
            action_type="webhook",
            name="Notify CRM",
            webhook_url="https://example.com/webhook",
        )

        assert result == expected_data
        call_args = mock_ghl_client._client.post.call_args
        json_data = call_args[1]["json"]
        assert json_data["type"] == "webhook"
        assert json_data["webhookUrl"] == "https://example.com/webhook"

    @pytest.mark.asyncio
    async def test_delete_action(self, mock_ghl_client, mock_response):
        """Test deleting an action."""
        expected_data = {"succeeded": True}
        mock_ghl_client._client.delete = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.voice_ai.delete_action(
            SAMPLE_AGENT_ID, SAMPLE_ACTION_ID
        )

        assert result == expected_data
        call_url = mock_ghl_client._client.delete.call_args[0][0]
        assert SAMPLE_AGENT_ID in call_url
        assert SAMPLE_ACTION_ID in call_url

    # =========================================================================
    # Call Log Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_list_calls(self, mock_ghl_client, mock_response):
        """Test listing call logs."""
        expected_data = {"calls": [MOCK_CALL], "total": 1}
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.voice_ai.list_calls()

        assert result == expected_data
        assert "voice-ai/calls" in mock_ghl_client._client.get.call_args[0][0]

    @pytest.mark.asyncio
    async def test_list_calls_with_filters(self, mock_ghl_client, mock_response):
        """Test listing calls with filters."""
        expected_data = {"calls": [MOCK_CALL], "total": 1}
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(expected_data)
        )

        await mock_ghl_client.voice_ai.list_calls(
            agent_id=SAMPLE_AGENT_ID,
            contact_id=SAMPLE_CONTACT_ID,
            status="completed",
            limit=25,
        )

        call_args = mock_ghl_client._client.get.call_args
        params = call_args[1]["params"]
        assert params["agentId"] == SAMPLE_AGENT_ID
        assert params["contactId"] == SAMPLE_CONTACT_ID
        assert params["status"] == "completed"
        assert params["limit"] == 25

    @pytest.mark.asyncio
    async def test_get_call_with_transcript(self, mock_ghl_client, mock_response):
        """Test getting a call with transcript."""
        expected_data = {"call": MOCK_CALL}
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.voice_ai.get_call(SAMPLE_CALL_ID)

        assert result == expected_data
        assert SAMPLE_CALL_ID in mock_ghl_client._client.get.call_args[0][0]
        # Verify transcript is included
        assert len(result["call"]["transcript"]) == 3
        assert result["call"]["summary"] is not None

    # =========================================================================
    # Phone Number Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_list_phone_numbers(self, mock_ghl_client, mock_response):
        """Test listing phone numbers."""
        expected_data = {"phoneNumbers": [MOCK_PHONE_NUMBER]}
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.voice_ai.list_phone_numbers()

        assert result == expected_data
        assert "phone-numbers" in mock_ghl_client._client.get.call_args[0][0]

    @pytest.mark.asyncio
    async def test_assign_phone_number(self, mock_ghl_client, mock_response):
        """Test assigning a phone number to an agent."""
        expected_data = {"agent": MOCK_VOICE_AI_AGENT}
        mock_ghl_client._client.patch = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.voice_ai.assign_phone_number(
            SAMPLE_AGENT_ID, SAMPLE_PHONE_ID
        )

        assert result == expected_data
        call_args = mock_ghl_client._client.patch.call_args
        assert SAMPLE_AGENT_ID in call_args[0][0]
        assert call_args[1]["json"]["phoneNumberId"] == SAMPLE_PHONE_ID

    # =========================================================================
    # Settings Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_settings(self, mock_ghl_client, mock_response):
        """Test getting voice AI settings."""
        expected_data = {"settings": MOCK_SETTINGS}
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.voice_ai.get_settings()

        assert result == expected_data
        assert "voice-ai/settings" in mock_ghl_client._client.get.call_args[0][0]

    @pytest.mark.asyncio
    async def test_update_settings_uses_patch(self, mock_ghl_client, mock_response):
        """Test that update_settings uses PATCH method."""
        expected_data = {"settings": MOCK_SETTINGS}
        mock_ghl_client._client.patch = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.voice_ai.update_settings(
            enabled=False,
        )

        assert result == expected_data
        mock_ghl_client._client.patch.assert_called_once()

    # =========================================================================
    # Error Handling Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_list_agents_no_location_id(self, mock_ghl_client):
        """Test that missing location_id raises error."""
        mock_ghl_client.config.location_id = None

        with pytest.raises(ValueError, match="location_id required"):
            await mock_ghl_client.voice_ai.list_agents()

    @pytest.mark.asyncio
    async def test_create_agent_no_location_id(self, mock_ghl_client):
        """Test that create without location_id raises error."""
        mock_ghl_client.config.location_id = None

        with pytest.raises(ValueError, match="location_id required"):
            await mock_ghl_client.voice_ai.create_agent(
                name="Test", voice_id=SAMPLE_VOICE_ID
            )


class TestVoiceAIEdgeCases:
    """Edge case tests for VoiceAIAPI."""

    @pytest.mark.asyncio
    async def test_list_agents_empty(self, mock_ghl_client, mock_response):
        """Test handling empty agent list."""
        expected_data = {"agents": [], "total": 0}
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.voice_ai.list_agents()

        assert result == expected_data
        assert result["agents"] == []
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_list_calls_empty(self, mock_ghl_client, mock_response):
        """Test handling no call history."""
        expected_data = {"calls": [], "total": 0}
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.voice_ai.list_calls()

        assert result == expected_data
        assert result["calls"] == []
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_get_call_no_transcript(self, mock_ghl_client, mock_response):
        """Test call without transcript."""
        call_without_transcript = {
            "id": SAMPLE_CALL_ID,
            "agentId": SAMPLE_AGENT_ID,
            "contactId": SAMPLE_CONTACT_ID,
            "status": "completed",
            "duration": 60,
            "transcript": [],
            "summary": None,
        }
        expected_data = {"call": call_without_transcript}
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.voice_ai.get_call(SAMPLE_CALL_ID)

        assert result["call"]["transcript"] == []
        assert result["call"]["summary"] is None

    @pytest.mark.asyncio
    async def test_agent_with_unicode_name(self, mock_ghl_client, mock_response):
        """Test agents with unicode characters in name."""
        unicode_agent = {
            "id": SAMPLE_AGENT_ID,
            "name": "Agente de Voz 日本語 🎙️",
            "voiceId": SAMPLE_VOICE_ID,
            "model": "gpt-4",
            "enabled": True,
            "locationId": SAMPLE_LOCATION_ID,
        }
        expected_data = {"agent": unicode_agent}
        mock_ghl_client._client.post = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.voice_ai.create_agent(
            name="Agente de Voz 日本語 🎙️",
            voice_id=SAMPLE_VOICE_ID,
        )

        assert result["agent"]["name"] == "Agente de Voz 日本語 🎙️"

    @pytest.mark.asyncio
    async def test_list_actions_empty(self, mock_ghl_client, mock_response):
        """Test handling agent with no actions."""
        expected_data = {"actions": []}
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.voice_ai.list_actions(SAMPLE_AGENT_ID)

        assert result == expected_data
        assert result["actions"] == []

    @pytest.mark.asyncio
    async def test_list_voices_empty(self, mock_ghl_client, mock_response):
        """Test handling no available voices."""
        expected_data = {"voices": []}
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.voice_ai.list_voices()

        assert result == expected_data
        assert result["voices"] == []

    @pytest.mark.asyncio
    async def test_agent_with_missing_optional_fields(self, mock_ghl_client, mock_response):
        """Test response with missing optional fields."""
        minimal_agent = {
            "id": SAMPLE_AGENT_ID,
            "name": "Minimal Voice Bot",
            "voiceId": SAMPLE_VOICE_ID,
            "locationId": SAMPLE_LOCATION_ID,
        }
        expected_data = {"agent": minimal_agent}
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.voice_ai.get_agent(SAMPLE_AGENT_ID)

        assert result["agent"]["id"] == SAMPLE_AGENT_ID
        assert result["agent"]["name"] == "Minimal Voice Bot"
        # Optional fields should not cause errors when missing
        assert "prompt" not in result["agent"]
        assert "greeting" not in result["agent"]
        assert "phoneNumberId" not in result["agent"]

    @pytest.mark.asyncio
    async def test_list_phone_numbers_empty(self, mock_ghl_client, mock_response):
        """Test handling no phone numbers available."""
        expected_data = {"phoneNumbers": []}
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.voice_ai.list_phone_numbers()

        assert result == expected_data
        assert result["phoneNumbers"] == []

