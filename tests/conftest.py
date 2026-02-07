"""Shared test fixtures for MaxLevel test suite."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any

# Sample IDs used across tests
SAMPLE_LOCATION_ID = "loc_test123"
SAMPLE_COMPANY_ID = "comp_test456"
SAMPLE_USER_ID = "user_test789"
SAMPLE_AGENT_ID = "agent_abc123"
SAMPLE_ACTION_ID = "action_def456"
SAMPLE_WORKFLOW_ID = "wf_ghi789"
SAMPLE_CONTACT_ID = "contact_jkl012"
SAMPLE_CALL_ID = "call_mno345"
SAMPLE_GENERATION_ID = "gen_pqr678"
SAMPLE_VOICE_ID = "voice_stu901"
SAMPLE_PHONE_ID = "phone_vwx234"


# ============================================================================
# Mock Response Data
# ============================================================================

MOCK_CONVERSATION_AI_AGENT = {
    "id": SAMPLE_AGENT_ID,
    "name": "Test Bot",
    "model": "gpt-4",
    "temperature": 0.7,
    "maxTokens": 500,
    "prompt": "You are a helpful assistant.",
    "enabled": True,
    "channels": ["sms", "email"],
    "locationId": SAMPLE_LOCATION_ID,
    "createdAt": "2024-01-15T10:00:00Z",
    "updatedAt": "2024-01-15T10:00:00Z",
}

MOCK_VOICE_AI_AGENT = {
    "id": SAMPLE_AGENT_ID,
    "name": "Voice Bot",
    "voiceId": SAMPLE_VOICE_ID,
    "model": "gpt-4",
    "temperature": 0.7,
    "prompt": "You schedule appointments.",
    "greeting": "Hello, how can I help you today?",
    "enabled": True,
    "phoneNumberId": SAMPLE_PHONE_ID,
    "locationId": SAMPLE_LOCATION_ID,
    "createdAt": "2024-01-15T10:00:00Z",
    "updatedAt": "2024-01-15T10:00:00Z",
}

MOCK_ACTION = {
    "id": SAMPLE_ACTION_ID,
    "type": "workflow",
    "actionId": SAMPLE_WORKFLOW_ID,
    "triggerCondition": "intent:book_appointment",
    "createdAt": "2024-01-15T10:00:00Z",
}

MOCK_GENERATION = {
    "id": SAMPLE_GENERATION_ID,
    "agentId": SAMPLE_AGENT_ID,
    "contactId": SAMPLE_CONTACT_ID,
    "conversationId": "conv_abc123",
    "input": "What are your hours?",
    "output": "We're open Monday to Friday, 9am to 5pm.",
    "tokensUsed": 45,
    "createdAt": "2024-01-15T10:30:00Z",
}

MOCK_CALL = {
    "id": SAMPLE_CALL_ID,
    "agentId": SAMPLE_AGENT_ID,
    "contactId": SAMPLE_CONTACT_ID,
    "status": "completed",
    "duration": 180,
    "transcript": [
        {"role": "assistant", "text": "Hello, how can I help you?"},
        {"role": "user", "text": "I'd like to book an appointment."},
        {"role": "assistant", "text": "I'd be happy to help with that."},
    ],
    "summary": "Customer called to schedule an appointment. Successfully booked for next Tuesday.",
    "recordingUrl": "https://example.com/recording.mp3",
    "createdAt": "2024-01-15T11:00:00Z",
}

MOCK_VOICE = {
    "id": SAMPLE_VOICE_ID,
    "name": "Sarah",
    "previewUrl": "https://example.com/preview.mp3",
    "gender": "female",
    "accent": "american",
}

MOCK_PHONE_NUMBER = {
    "id": SAMPLE_PHONE_ID,
    "phone": "+15551234567",
    "agentId": SAMPLE_AGENT_ID,
}

MOCK_SETTINGS = {
    "enabled": True,
    "defaultModel": "gpt-4",
    "defaultTemperature": 0.7,
}


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_config():
    """Create a mock GHLConfig."""
    from maxlevel.api.client import GHLConfig
    return GHLConfig(
        token="test_token_abc123",
        user_id=SAMPLE_USER_ID,
        company_id=SAMPLE_COMPANY_ID,
        location_id=SAMPLE_LOCATION_ID,
    )


@pytest.fixture
def mock_http_client():
    """Create a mock httpx.AsyncClient."""
    client = AsyncMock()

    # Default successful response
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {}
    response.raise_for_status = MagicMock()

    client.get = AsyncMock(return_value=response)
    client.post = AsyncMock(return_value=response)
    client.put = AsyncMock(return_value=response)
    client.patch = AsyncMock(return_value=response)
    client.delete = AsyncMock(return_value=response)

    return client


@pytest.fixture
def mock_ghl_client(mock_config, mock_http_client):
    """Create a mock GHLClient with initialized APIs."""
    from maxlevel.api.client import GHLClient
    from maxlevel.api.conversation_ai import ConversationAIAPI
    from maxlevel.api.voice_ai import VoiceAIAPI
    from maxlevel.api.agency import AgencyAPI

    client = GHLClient(mock_config)
    client._client = mock_http_client
    client._conversation_ai = ConversationAIAPI(client)
    client._voice_ai = VoiceAIAPI(client)
    client._agency = AgencyAPI(client)

    return client


@pytest.fixture
def mock_response():
    """Factory fixture to create mock HTTP responses."""
    def _create_response(data: dict[str, Any], status_code: int = 200):
        response = MagicMock()
        response.status_code = status_code
        response.json.return_value = data
        response.raise_for_status = MagicMock()
        if status_code >= 400:
            from httpx import HTTPStatusError
            response.raise_for_status.side_effect = HTTPStatusError(
                f"HTTP {status_code}", request=MagicMock(), response=response
            )
        return response
    return _create_response


@pytest.fixture
def mock_error_response():
    """Factory fixture to create common error responses."""
    def _create_error(error_type: str):
        from httpx import HTTPStatusError

        error_configs = {
            "not_found": {
                "status_code": 404,
                "data": {"error": "Resource not found", "message": "Agent not found"},
            },
            "validation": {
                "status_code": 400,
                "data": {"error": "Validation error", "message": "Invalid request data"},
            },
            "unauthorized": {
                "status_code": 401,
                "data": {"error": "Unauthorized", "message": "Invalid or expired token"},
            },
            "rate_limit": {
                "status_code": 429,
                "data": {"error": "Rate limit exceeded", "message": "Too many requests"},
            },
            "server_error": {
                "status_code": 500,
                "data": {"error": "Internal server error", "message": "An unexpected error occurred"},
            },
        }

        config = error_configs.get(error_type, error_configs["server_error"])
        response = MagicMock()
        response.status_code = config["status_code"]
        response.json.return_value = config["data"]
        response.text = str(config["data"])
        response.raise_for_status = MagicMock(
            side_effect=HTTPStatusError(
                f"HTTP {config['status_code']}",
                request=MagicMock(),
                response=response
            )
        )
        return response
    return _create_error


# ============================================================================
# CLI Testing Fixtures
# ============================================================================

@pytest.fixture
def cli_runner():
    """Create a Typer CLI test runner."""
    from typer.testing import CliRunner
    return CliRunner()


@pytest.fixture
def mock_ghl_client_context():
    """Context manager mock for GHLClient.from_session()."""
    mock_client = MagicMock()
    mock_client.config = MagicMock()
    mock_client.config.location_id = SAMPLE_LOCATION_ID

    # Mock conversation_ai
    mock_client.conversation_ai = AsyncMock()
    mock_client.conversation_ai.list_agents = AsyncMock(return_value={
        "agents": [MOCK_CONVERSATION_AI_AGENT],
        "total": 1,
    })
    mock_client.conversation_ai.get_agent = AsyncMock(return_value={
        "agent": MOCK_CONVERSATION_AI_AGENT,
    })
    mock_client.conversation_ai.create_agent = AsyncMock(return_value={
        "agent": MOCK_CONVERSATION_AI_AGENT,
    })
    mock_client.conversation_ai.update_agent = AsyncMock(return_value={
        "agent": MOCK_CONVERSATION_AI_AGENT,
    })
    mock_client.conversation_ai.delete_agent = AsyncMock(return_value={
        "succeeded": True,
    })
    mock_client.conversation_ai.list_actions = AsyncMock(return_value={
        "actions": [MOCK_ACTION],
    })
    mock_client.conversation_ai.attach_action = AsyncMock(return_value={
        "action": MOCK_ACTION,
    })
    mock_client.conversation_ai.remove_action = AsyncMock(return_value={
        "succeeded": True,
    })
    mock_client.conversation_ai.list_generations = AsyncMock(return_value={
        "generations": [MOCK_GENERATION],
        "total": 1,
    })
    mock_client.conversation_ai.get_settings = AsyncMock(return_value={
        "settings": MOCK_SETTINGS,
    })

    # Mock voice_ai
    mock_client.voice_ai = AsyncMock()
    mock_client.voice_ai.list_agents = AsyncMock(return_value={
        "agents": [MOCK_VOICE_AI_AGENT],
        "total": 1,
    })
    mock_client.voice_ai.get_agent = AsyncMock(return_value={
        "agent": MOCK_VOICE_AI_AGENT,
    })
    mock_client.voice_ai.create_agent = AsyncMock(return_value={
        "agent": MOCK_VOICE_AI_AGENT,
    })
    mock_client.voice_ai.update_agent = AsyncMock(return_value={
        "agent": MOCK_VOICE_AI_AGENT,
    })
    mock_client.voice_ai.delete_agent = AsyncMock(return_value={
        "succeeded": True,
    })
    mock_client.voice_ai.list_voices = AsyncMock(return_value={
        "voices": [MOCK_VOICE],
    })
    mock_client.voice_ai.list_calls = AsyncMock(return_value={
        "calls": [MOCK_CALL],
        "total": 1,
    })
    mock_client.voice_ai.get_call = AsyncMock(return_value={
        "call": MOCK_CALL,
    })
    mock_client.voice_ai.list_actions = AsyncMock(return_value={
        "actions": [MOCK_ACTION],
    })
    mock_client.voice_ai.create_action = AsyncMock(return_value={
        "action": MOCK_ACTION,
    })
    mock_client.voice_ai.delete_action = AsyncMock(return_value={
        "succeeded": True,
    })
    mock_client.voice_ai.get_settings = AsyncMock(return_value={
        "settings": MOCK_SETTINGS,
    })
    mock_client.voice_ai.list_phone_numbers = AsyncMock(return_value={
        "phoneNumbers": [MOCK_PHONE_NUMBER],
    })

    # Mock agency
    mock_client.agency = AsyncMock()
    mock_client.agency.list_locations = AsyncMock(return_value={
        "locations": [
            {
                "_id": SAMPLE_LOCATION_ID,
                "name": "Test Business",
                "email": "test@example.com",
                "timezone": "America/New_York",
            }
        ],
        "total": 1,
    })
    mock_client.agency.get_location = AsyncMock(return_value={
        "location": {
            "_id": SAMPLE_LOCATION_ID,
            "name": "Test Business",
            "email": "test@example.com",
        },
    })
    mock_client.agency.create_location = AsyncMock(return_value={
        "location": {
            "_id": "new_loc_123",
            "name": "New Business",
        },
    })
    mock_client.agency.update_location = AsyncMock(return_value={
        "location": {
            "_id": SAMPLE_LOCATION_ID,
            "name": "Updated Business",
        },
    })
    mock_client.agency.delete_location = AsyncMock(return_value={
        "succeeded": True,
    })
    mock_client.agency.list_snapshots = AsyncMock(return_value={
        "snapshots": [{"_id": "snap_123", "name": "Default Snapshot"}],
        "total": 1,
    })
    mock_client.agency.list_users = AsyncMock(return_value={
        "users": [
            {
                "_id": SAMPLE_USER_ID,
                "firstName": "John",
                "lastName": "Doe",
                "email": "john@example.com",
                "role": "admin",
            }
        ],
        "total": 1,
    })
    mock_client.agency.invite_user = AsyncMock(return_value={
        "user": {
            "_id": "new_user_123",
            "email": "invite@example.com",
        },
    })
    mock_client.agency.get_agency_plan = AsyncMock(return_value={
        "name": "Agency Pro",
        "status": "active",
    })
    mock_client.agency.get_location_limits = AsyncMock(return_value={
        "used": 5,
        "limit": 10,
        "remaining": 5,
    })

    return mock_client


# ============================================================================
# Browser Automation Fixtures
# ============================================================================

@pytest.fixture
def mock_tab_id():
    """Sample Chrome MCP tab ID."""
    return 12345
