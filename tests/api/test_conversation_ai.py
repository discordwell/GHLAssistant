"""Tests for Conversation AI API module."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from ghl_assistant.api.conversation_ai import ConversationAIAPI
from tests.conftest import (
    SAMPLE_LOCATION_ID,
    SAMPLE_AGENT_ID,
    SAMPLE_ACTION_ID,
    SAMPLE_WORKFLOW_ID,
    SAMPLE_CONTACT_ID,
    SAMPLE_GENERATION_ID,
    MOCK_CONVERSATION_AI_AGENT,
    MOCK_ACTION,
    MOCK_GENERATION,
    MOCK_SETTINGS,
)


class TestConversationAIAPI:
    """Test suite for ConversationAIAPI class."""

    # =========================================================================
    # Agent Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_list_agents(self, mock_ghl_client, mock_response):
        """Test listing conversation AI agents."""
        expected_data = {"agents": [MOCK_CONVERSATION_AI_AGENT], "total": 1}
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.conversation_ai.list_agents()

        assert result == expected_data
        mock_ghl_client._client.get.assert_called_once()
        call_args = mock_ghl_client._client.get.call_args
        assert "conversation-ai/agents" in call_args[0][0]
        assert call_args[1]["params"]["locationId"] == SAMPLE_LOCATION_ID

    @pytest.mark.asyncio
    async def test_list_agents_with_pagination(self, mock_ghl_client, mock_response):
        """Test listing agents with limit and skip parameters."""
        expected_data = {"agents": [], "total": 0}
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(expected_data)
        )

        await mock_ghl_client.conversation_ai.list_agents(limit=10, skip=20)

        call_args = mock_ghl_client._client.get.call_args
        assert call_args[1]["params"]["limit"] == 10
        assert call_args[1]["params"]["skip"] == 20

    @pytest.mark.asyncio
    async def test_list_agents_with_custom_location(self, mock_ghl_client, mock_response):
        """Test listing agents for a specific location."""
        custom_location = "custom_loc_123"
        expected_data = {"agents": [], "total": 0}
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(expected_data)
        )

        await mock_ghl_client.conversation_ai.list_agents(location_id=custom_location)

        call_args = mock_ghl_client._client.get.call_args
        assert call_args[1]["params"]["locationId"] == custom_location

    @pytest.mark.asyncio
    async def test_get_agent(self, mock_ghl_client, mock_response):
        """Test getting a single agent by ID."""
        expected_data = {"agent": MOCK_CONVERSATION_AI_AGENT}
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.conversation_ai.get_agent(SAMPLE_AGENT_ID)

        assert result == expected_data
        mock_ghl_client._client.get.assert_called_once()
        assert SAMPLE_AGENT_ID in mock_ghl_client._client.get.call_args[0][0]

    @pytest.mark.asyncio
    async def test_create_agent_minimal(self, mock_ghl_client, mock_response):
        """Test creating an agent with minimal parameters."""
        expected_data = {"agent": MOCK_CONVERSATION_AI_AGENT}
        mock_ghl_client._client.post = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.conversation_ai.create_agent(name="Test Bot")

        assert result == expected_data
        mock_ghl_client._client.post.assert_called_once()
        call_args = mock_ghl_client._client.post.call_args
        assert call_args[1]["json"]["name"] == "Test Bot"
        assert call_args[1]["json"]["model"] == "gpt-4"  # Default
        assert call_args[1]["json"]["temperature"] == 0.7  # Default
        assert call_args[1]["json"]["locationId"] == SAMPLE_LOCATION_ID

    @pytest.mark.asyncio
    async def test_create_agent_full(self, mock_ghl_client, mock_response):
        """Test creating an agent with all parameters."""
        expected_data = {"agent": MOCK_CONVERSATION_AI_AGENT}
        mock_ghl_client._client.post = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.conversation_ai.create_agent(
            name="Full Bot",
            prompt="You are helpful.",
            model="gpt-3.5-turbo",
            temperature=0.5,
            max_tokens=1000,
            channels=["sms", "email", "webchat"],
        )

        assert result == expected_data
        call_args = mock_ghl_client._client.post.call_args
        json_data = call_args[1]["json"]
        assert json_data["name"] == "Full Bot"
        assert json_data["prompt"] == "You are helpful."
        assert json_data["model"] == "gpt-3.5-turbo"
        assert json_data["temperature"] == 0.5
        assert json_data["maxTokens"] == 1000
        assert json_data["channels"] == ["sms", "email", "webchat"]

    @pytest.mark.asyncio
    async def test_update_agent(self, mock_ghl_client, mock_response):
        """Test updating an agent."""
        expected_data = {"agent": MOCK_CONVERSATION_AI_AGENT}
        mock_ghl_client._client.put = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.conversation_ai.update_agent(
            SAMPLE_AGENT_ID,
            name="Updated Bot",
            enabled=False,
        )

        assert result == expected_data
        call_args = mock_ghl_client._client.put.call_args
        assert SAMPLE_AGENT_ID in call_args[0][0]
        assert call_args[1]["json"]["name"] == "Updated Bot"
        assert call_args[1]["json"]["enabled"] is False

    @pytest.mark.asyncio
    async def test_update_agent_partial(self, mock_ghl_client, mock_response):
        """Test updating only specific fields."""
        expected_data = {"agent": MOCK_CONVERSATION_AI_AGENT}
        mock_ghl_client._client.put = AsyncMock(
            return_value=mock_response(expected_data)
        )

        await mock_ghl_client.conversation_ai.update_agent(
            SAMPLE_AGENT_ID,
            temperature=0.9,
        )

        call_args = mock_ghl_client._client.put.call_args
        json_data = call_args[1]["json"]
        assert json_data["temperature"] == 0.9
        assert "name" not in json_data
        assert "prompt" not in json_data

    @pytest.mark.asyncio
    async def test_delete_agent(self, mock_ghl_client, mock_response):
        """Test deleting an agent."""
        expected_data = {"succeeded": True}
        mock_ghl_client._client.delete = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.conversation_ai.delete_agent(SAMPLE_AGENT_ID)

        assert result == expected_data
        assert SAMPLE_AGENT_ID in mock_ghl_client._client.delete.call_args[0][0]

    # =========================================================================
    # Action Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_list_actions(self, mock_ghl_client, mock_response):
        """Test listing agent actions."""
        expected_data = {"actions": [MOCK_ACTION]}
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.conversation_ai.list_actions(SAMPLE_AGENT_ID)

        assert result == expected_data
        call_url = mock_ghl_client._client.get.call_args[0][0]
        assert SAMPLE_AGENT_ID in call_url
        assert "actions" in call_url

    @pytest.mark.asyncio
    async def test_attach_action(self, mock_ghl_client, mock_response):
        """Test attaching an action to an agent."""
        expected_data = {"action": MOCK_ACTION}
        mock_ghl_client._client.post = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.conversation_ai.attach_action(
            SAMPLE_AGENT_ID,
            SAMPLE_WORKFLOW_ID,
            action_type="workflow",
            trigger_condition="intent:book",
        )

        assert result == expected_data
        call_args = mock_ghl_client._client.post.call_args
        assert SAMPLE_AGENT_ID in call_args[0][0]
        json_data = call_args[1]["json"]
        assert json_data["actionId"] == SAMPLE_WORKFLOW_ID
        assert json_data["type"] == "workflow"
        assert json_data["triggerCondition"] == "intent:book"

    @pytest.mark.asyncio
    async def test_remove_action(self, mock_ghl_client, mock_response):
        """Test removing an action from an agent."""
        expected_data = {"succeeded": True}
        mock_ghl_client._client.delete = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.conversation_ai.remove_action(
            SAMPLE_AGENT_ID, SAMPLE_ACTION_ID
        )

        assert result == expected_data
        call_url = mock_ghl_client._client.delete.call_args[0][0]
        assert SAMPLE_AGENT_ID in call_url
        assert SAMPLE_ACTION_ID in call_url

    # =========================================================================
    # Generation History Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_list_generations(self, mock_ghl_client, mock_response):
        """Test listing AI generations."""
        expected_data = {"generations": [MOCK_GENERATION], "total": 1}
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.conversation_ai.list_generations()

        assert result == expected_data
        assert "generations" in mock_ghl_client._client.get.call_args[0][0]

    @pytest.mark.asyncio
    async def test_list_generations_with_filters(self, mock_ghl_client, mock_response):
        """Test listing generations with filters."""
        expected_data = {"generations": [MOCK_GENERATION], "total": 1}
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(expected_data)
        )

        await mock_ghl_client.conversation_ai.list_generations(
            agent_id=SAMPLE_AGENT_ID,
            contact_id=SAMPLE_CONTACT_ID,
            limit=25,
        )

        call_args = mock_ghl_client._client.get.call_args
        params = call_args[1]["params"]
        assert params["agentId"] == SAMPLE_AGENT_ID
        assert params["contactId"] == SAMPLE_CONTACT_ID
        assert params["limit"] == 25

    @pytest.mark.asyncio
    async def test_get_generation(self, mock_ghl_client, mock_response):
        """Test getting a single generation."""
        expected_data = {"generation": MOCK_GENERATION}
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.conversation_ai.get_generation(SAMPLE_GENERATION_ID)

        assert result == expected_data
        assert SAMPLE_GENERATION_ID in mock_ghl_client._client.get.call_args[0][0]

    # =========================================================================
    # Conversations Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_list_conversations(self, mock_ghl_client, mock_response):
        """Test listing agent conversations."""
        expected_data = {"conversations": [], "total": 0}
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.conversation_ai.list_conversations(SAMPLE_AGENT_ID)

        assert result == expected_data
        call_url = mock_ghl_client._client.get.call_args[0][0]
        assert SAMPLE_AGENT_ID in call_url
        assert "conversations" in call_url

    # =========================================================================
    # Settings Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_settings(self, mock_ghl_client, mock_response):
        """Test getting AI settings."""
        expected_data = {"settings": MOCK_SETTINGS}
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.conversation_ai.get_settings()

        assert result == expected_data
        assert "settings" in mock_ghl_client._client.get.call_args[0][0]

    @pytest.mark.asyncio
    async def test_update_settings(self, mock_ghl_client, mock_response):
        """Test updating AI settings."""
        expected_data = {"settings": MOCK_SETTINGS}
        mock_ghl_client._client.put = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.conversation_ai.update_settings(
            defaultModel="gpt-3.5-turbo",
        )

        assert result == expected_data
        call_args = mock_ghl_client._client.put.call_args
        assert call_args[1]["json"]["defaultModel"] == "gpt-3.5-turbo"

    # =========================================================================
    # Error Handling Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_list_agents_no_location_id(self, mock_ghl_client):
        """Test that missing location_id raises error."""
        mock_ghl_client.config.location_id = None

        with pytest.raises(ValueError, match="location_id required"):
            await mock_ghl_client.conversation_ai.list_agents()

    @pytest.mark.asyncio
    async def test_create_agent_no_location_id(self, mock_ghl_client):
        """Test that create without location_id raises error."""
        mock_ghl_client.config.location_id = None

        with pytest.raises(ValueError, match="location_id required"):
            await mock_ghl_client.conversation_ai.create_agent(name="Test")


class TestConversationAIEdgeCases:
    """Edge case tests for ConversationAIAPI."""

    @pytest.mark.asyncio
    async def test_list_agents_empty(self, mock_ghl_client, mock_response):
        """Test handling empty agent list."""
        expected_data = {"agents": [], "total": 0}
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.conversation_ai.list_agents()

        assert result == expected_data
        assert result["agents"] == []
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_list_actions_empty(self, mock_ghl_client, mock_response):
        """Test handling agent with no actions."""
        expected_data = {"actions": []}
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.conversation_ai.list_actions(SAMPLE_AGENT_ID)

        assert result == expected_data
        assert result["actions"] == []

    @pytest.mark.asyncio
    async def test_list_generations_empty(self, mock_ghl_client, mock_response):
        """Test handling no generation history."""
        expected_data = {"generations": [], "total": 0}
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.conversation_ai.list_generations()

        assert result == expected_data
        assert result["generations"] == []
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_agent_with_unicode_name(self, mock_ghl_client, mock_response):
        """Test agents with unicode characters in name."""
        unicode_agent = {
            "id": SAMPLE_AGENT_ID,
            "name": "Bot de Atención 日本語 🤖",
            "model": "gpt-4",
            "temperature": 0.7,
            "enabled": True,
            "locationId": SAMPLE_LOCATION_ID,
        }
        expected_data = {"agent": unicode_agent}
        mock_ghl_client._client.post = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.conversation_ai.create_agent(
            name="Bot de Atención 日本語 🤖"
        )

        assert result["agent"]["name"] == "Bot de Atención 日本語 🤖"

    @pytest.mark.asyncio
    async def test_agent_with_very_long_prompt(self, mock_ghl_client, mock_response):
        """Test agents with maximum length prompts."""
        long_prompt = "You are a helpful assistant. " * 1000
        expected_data = {"agent": {**MOCK_CONVERSATION_AI_AGENT, "prompt": long_prompt}}
        mock_ghl_client._client.post = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.conversation_ai.create_agent(
            name="Long Prompt Bot",
            prompt=long_prompt,
        )

        call_args = mock_ghl_client._client.post.call_args
        assert call_args[1]["json"]["prompt"] == long_prompt

    @pytest.mark.asyncio
    async def test_agent_with_missing_optional_fields(self, mock_ghl_client, mock_response):
        """Test response with missing optional fields."""
        minimal_agent = {
            "id": SAMPLE_AGENT_ID,
            "name": "Minimal Bot",
            "locationId": SAMPLE_LOCATION_ID,
        }
        expected_data = {"agent": minimal_agent}
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.conversation_ai.get_agent(SAMPLE_AGENT_ID)

        assert result["agent"]["id"] == SAMPLE_AGENT_ID
        assert result["agent"]["name"] == "Minimal Bot"
        # Optional fields should not cause errors when missing
        assert "prompt" not in result["agent"]
        assert "temperature" not in result["agent"]

    @pytest.mark.asyncio
    async def test_list_conversations_empty(self, mock_ghl_client, mock_response):
        """Test handling agent with no conversations."""
        expected_data = {"conversations": [], "total": 0}
        mock_ghl_client._client.get = AsyncMock(
            return_value=mock_response(expected_data)
        )

        result = await mock_ghl_client.conversation_ai.list_conversations(SAMPLE_AGENT_ID)

        assert result == expected_data
        assert result["conversations"] == []

