"""Tests for Voice AI CLI commands."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from typer.testing import CliRunner

from ghl_assistant.cli import app
from tests.conftest import (
    SAMPLE_AGENT_ID,
    SAMPLE_ACTION_ID,
    SAMPLE_WORKFLOW_ID,
    SAMPLE_CALL_ID,
    SAMPLE_VOICE_ID,
    MOCK_VOICE_AI_AGENT,
    MOCK_ACTION,
    MOCK_CALL,
    MOCK_VOICE,
    MOCK_PHONE_NUMBER,
    MOCK_SETTINGS,
)


@pytest.fixture
def mock_client_factory(mock_ghl_client_context):
    """Create a factory that produces mock GHLClient context managers."""
    def _create():
        mock_instance = MagicMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_ghl_client_context)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        return mock_instance
    return _create


class TestVoiceListCommand:
    """Tests for 'ghl voice list' command."""

    def test_list_agents(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test listing voice AI agents."""
        with patch("ghl_assistant.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, ["voice", "list"])

            assert result.exit_code == 0
            assert "Voice AI Agents" in result.output
            assert "Voice Bot" in result.output
            mock_ghl_client_context.voice_ai.list_agents.assert_called_with(limit=50)

    def test_list_agents_json(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test listing agents with JSON output."""
        with patch("ghl_assistant.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, ["voice", "list", "--json"])

            assert result.exit_code == 0
            assert '"agents"' in result.output
            mock_ghl_client_context.voice_ai.list_agents.assert_called_with(limit=50)


class TestVoiceGetCommand:
    """Tests for 'ghl voice get' command."""

    def test_get_agent(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test getting a single voice agent."""
        with patch("ghl_assistant.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, ["voice", "get", SAMPLE_AGENT_ID])

            assert result.exit_code == 0
            mock_ghl_client_context.voice_ai.get_agent.assert_called_with(SAMPLE_AGENT_ID)
            # Verify output contains agent data
            assert "Voice Bot" in result.output or SAMPLE_AGENT_ID in result.output


class TestVoiceCreateCommand:
    """Tests for 'ghl voice create' command."""

    def test_create_agent_minimal(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test creating a voice agent with minimal parameters."""
        with patch("ghl_assistant.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, ["voice", "create", "Test Voice", SAMPLE_VOICE_ID])

            assert result.exit_code == 0
            assert "created" in result.output.lower()
            # CLI passes all parameters including defaults
            mock_ghl_client_context.voice_ai.create_agent.assert_called_with(
                name="Test Voice",
                voice_id=SAMPLE_VOICE_ID,
                prompt=None,
                greeting=None,
                model="gpt-4",
                temperature=0.7,
            )

    def test_create_agent_full(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test creating a voice agent with all parameters."""
        with patch("ghl_assistant.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, [
                "voice", "create", "Full Voice", SAMPLE_VOICE_ID,
                "--prompt", "You are a receptionist.",
                "--greeting", "Hello, how can I help?",
                "--model", "gpt-3.5-turbo",
                "--temperature", "0.5",
            ])

            assert result.exit_code == 0
            mock_ghl_client_context.voice_ai.create_agent.assert_called_with(
                name="Full Voice",
                voice_id=SAMPLE_VOICE_ID,
                prompt="You are a receptionist.",
                greeting="Hello, how can I help?",
                model="gpt-3.5-turbo",
                temperature=0.5,
            )


class TestVoiceUpdateCommand:
    """Tests for 'ghl voice update' command."""

    def test_update_agent(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test updating a voice agent."""
        with patch("ghl_assistant.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, [
                "voice", "update", SAMPLE_AGENT_ID,
                "--name", "Updated Voice",
            ])

            assert result.exit_code == 0
            assert "updated" in result.output.lower()
            mock_ghl_client_context.voice_ai.update_agent.assert_called_with(
                SAMPLE_AGENT_ID,
                name="Updated Voice",
                voice_id=None,
                prompt=None,
                greeting=None,
                enabled=None,
            )

    def test_update_agent_voice(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test updating agent voice."""
        with patch("ghl_assistant.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, [
                "voice", "update", SAMPLE_AGENT_ID,
                "--voice", "new_voice_id",
            ])

            assert result.exit_code == 0
            mock_ghl_client_context.voice_ai.update_agent.assert_called_with(
                SAMPLE_AGENT_ID,
                name=None,
                voice_id="new_voice_id",
                prompt=None,
                greeting=None,
                enabled=None,
            )


class TestVoiceDeleteCommand:
    """Tests for 'ghl voice delete' command."""

    def test_delete_agent_with_confirmation(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test deleting a voice agent with confirmation."""
        with patch("ghl_assistant.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, ["voice", "delete", SAMPLE_AGENT_ID], input="y\n")

            assert result.exit_code == 0
            assert "deleted" in result.output.lower()

    def test_delete_agent_skip_confirmation(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test deleting with --yes flag."""
        with patch("ghl_assistant.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, ["voice", "delete", SAMPLE_AGENT_ID, "--yes"])

            assert result.exit_code == 0
            assert "deleted" in result.output.lower()

    def test_delete_agent_abort(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test aborting voice agent deletion."""
        with patch("ghl_assistant.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, ["voice", "delete", SAMPLE_AGENT_ID], input="n\n")

            assert result.exit_code == 0
            assert "aborted" in result.output.lower()


class TestVoiceVoicesCommand:
    """Tests for 'ghl voice voices' command."""

    def test_list_voices(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test listing available voices."""
        with patch("ghl_assistant.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, ["voice", "voices"])

            assert result.exit_code == 0
            assert "Available Voices" in result.output
            assert "Sarah" in result.output
            mock_ghl_client_context.voice_ai.list_voices.assert_called_once()

    def test_list_voices_json(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test listing voices with JSON output."""
        with patch("ghl_assistant.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, ["voice", "voices", "--json"])

            assert result.exit_code == 0
            assert '"voices"' in result.output
            # Verify JSON contains voice data
            assert SAMPLE_VOICE_ID in result.output or '"Sarah"' in result.output


class TestVoiceCallsCommand:
    """Tests for 'ghl voice calls' command."""

    def test_list_calls(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test listing call logs."""
        with patch("ghl_assistant.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, ["voice", "calls"])

            assert result.exit_code == 0
            assert "Voice AI Calls" in result.output
            mock_ghl_client_context.voice_ai.list_calls.assert_called_with(
                agent_id=None,
                contact_id=None,
                status=None,
                limit=50,
            )

    def test_list_calls_with_filters(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test listing calls with filters."""
        with patch("ghl_assistant.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, [
                "voice", "calls",
                "--agent", SAMPLE_AGENT_ID,
                "--status", "completed",
                "--limit", "25",
            ])

            assert result.exit_code == 0
            mock_ghl_client_context.voice_ai.list_calls.assert_called_with(
                agent_id=SAMPLE_AGENT_ID,
                contact_id=None,
                status="completed",
                limit=25,
            )


class TestVoiceTranscriptCommand:
    """Tests for 'ghl voice transcript' command."""

    def test_get_transcript(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test getting call transcript."""
        with patch("ghl_assistant.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, ["voice", "transcript", SAMPLE_CALL_ID])

            assert result.exit_code == 0
            assert "Call Details" in result.output or "Transcript" in result.output
            mock_ghl_client_context.voice_ai.get_call.assert_called_with(SAMPLE_CALL_ID)
            # Verify transcript content is displayed
            assert "appointment" in result.output.lower() or "hello" in result.output.lower()

    def test_get_transcript_json(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test getting transcript with JSON output."""
        with patch("ghl_assistant.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, ["voice", "transcript", SAMPLE_CALL_ID, "--json"])

            assert result.exit_code == 0
            # Verify JSON structure
            assert '"call"' in result.output or '"transcript"' in result.output


class TestVoiceActionsCommand:
    """Tests for 'ghl voice actions' command."""

    def test_list_actions(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test listing voice agent actions."""
        with patch("ghl_assistant.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, ["voice", "actions", SAMPLE_AGENT_ID])

            assert result.exit_code == 0
            assert "Voice Agent Actions" in result.output
            mock_ghl_client_context.voice_ai.list_actions.assert_called_with(SAMPLE_AGENT_ID)


class TestVoiceAddActionCommand:
    """Tests for 'ghl voice add-action' command."""

    def test_add_workflow_action(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test adding a workflow action."""
        with patch("ghl_assistant.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, [
                "voice", "add-action", SAMPLE_AGENT_ID,
                "workflow", "Book Appointment",
                "--workflow", SAMPLE_WORKFLOW_ID,
            ])

            assert result.exit_code == 0
            assert "added" in result.output.lower()
            mock_ghl_client_context.voice_ai.create_action.assert_called_with(
                SAMPLE_AGENT_ID,
                action_type="workflow",
                name="Book Appointment",
                trigger_condition=None,
                workflow_id=SAMPLE_WORKFLOW_ID,
                webhook_url=None,
            )

    def test_add_webhook_action(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test adding a webhook action."""
        with patch("ghl_assistant.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, [
                "voice", "add-action", SAMPLE_AGENT_ID,
                "webhook", "Notify CRM",
                "--webhook", "https://example.com/webhook",
            ])

            assert result.exit_code == 0
            assert "added" in result.output.lower()
            mock_ghl_client_context.voice_ai.create_action.assert_called_with(
                SAMPLE_AGENT_ID,
                action_type="webhook",
                name="Notify CRM",
                trigger_condition=None,
                workflow_id=None,
                webhook_url="https://example.com/webhook",
            )

    def test_add_action_with_trigger(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test adding an action with trigger condition."""
        with patch("ghl_assistant.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, [
                "voice", "add-action", SAMPLE_AGENT_ID,
                "workflow", "Schedule",
                "--trigger", "intent:schedule_appointment",
                "--workflow", SAMPLE_WORKFLOW_ID,
            ])

            assert result.exit_code == 0
            mock_ghl_client_context.voice_ai.create_action.assert_called_with(
                SAMPLE_AGENT_ID,
                action_type="workflow",
                name="Schedule",
                trigger_condition="intent:schedule_appointment",
                workflow_id=SAMPLE_WORKFLOW_ID,
                webhook_url=None,
            )


class TestVoiceRemoveActionCommand:
    """Tests for 'ghl voice remove-action' command."""

    def test_remove_action(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test removing an action."""
        with patch("ghl_assistant.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, [
                "voice", "remove-action", SAMPLE_AGENT_ID, SAMPLE_ACTION_ID,
            ])

            assert result.exit_code == 0
            assert "removed" in result.output.lower()
            mock_ghl_client_context.voice_ai.delete_action.assert_called_with(
                SAMPLE_AGENT_ID,
                SAMPLE_ACTION_ID,
            )


class TestVoiceSettingsCommand:
    """Tests for 'ghl voice settings' command."""

    def test_get_settings(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test getting voice AI settings."""
        with patch("ghl_assistant.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, ["voice", "settings"])

            assert result.exit_code == 0
            mock_ghl_client_context.voice_ai.get_settings.assert_called_once()
            # Verify output displays settings info
            assert "gpt-4" in result.output or "enabled" in result.output.lower()


class TestVoicePhonesCommand:
    """Tests for 'ghl voice phones' command."""

    def test_list_phones(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test listing phone numbers."""
        with patch("ghl_assistant.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, ["voice", "phones"])

            assert result.exit_code == 0
            assert "Phone Numbers" in result.output
            mock_ghl_client_context.voice_ai.list_phone_numbers.assert_called_once()
            # Verify phone data displayed
            assert "+15551234567" in result.output or SAMPLE_PHONE_ID in result.output

    def test_list_phones_json(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test listing phones with JSON output."""
        with patch("ghl_assistant.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, ["voice", "phones", "--json"])

            assert result.exit_code == 0
            # Verify JSON structure
            assert '"phoneNumbers"' in result.output or '"phone"' in result.output


class TestVoiceCommandHelp:
    """Tests for Voice command help output."""

    def test_voice_help(self, cli_runner):
        """Test 'ghl voice --help' shows all commands."""
        result = cli_runner.invoke(app, ["voice", "--help"])

        assert result.exit_code == 0
        assert "list" in result.output
        assert "get" in result.output
        assert "create" in result.output
        assert "update" in result.output
        assert "delete" in result.output
        assert "voices" in result.output
        assert "calls" in result.output
        assert "transcript" in result.output
        assert "actions" in result.output
        assert "add-action" in result.output
        assert "remove-action" in result.output
        assert "settings" in result.output
        assert "phones" in result.output

    def test_voice_create_help(self, cli_runner):
        """Test 'ghl voice create --help' shows options."""
        result = cli_runner.invoke(app, ["voice", "create", "--help"])

        assert result.exit_code == 0
        assert "--prompt" in result.output
        assert "--greeting" in result.output
        assert "--model" in result.output
        assert "--temperature" in result.output
        assert "voice_id" in result.output.lower()


class TestVoiceCommandErrors:
    """Tests for Voice command error handling."""

    def test_list_agents_api_error(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test CLI handles API errors gracefully."""
        from httpx import HTTPStatusError

        mock_ghl_client_context.voice_ai.list_agents = AsyncMock(
            side_effect=HTTPStatusError(
                "HTTP 500", request=MagicMock(), response=MagicMock(status_code=500)
            )
        )

        with patch("ghl_assistant.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, ["voice", "list"])

            # Should handle error gracefully
            assert result.exit_code != 0 or "error" in result.output.lower()

    def test_get_agent_not_found(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test CLI handles 404 error for non-existent agent."""
        from httpx import HTTPStatusError

        mock_ghl_client_context.voice_ai.get_agent = AsyncMock(
            side_effect=HTTPStatusError(
                "HTTP 404", request=MagicMock(), response=MagicMock(status_code=404)
            )
        )

        with patch("ghl_assistant.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, ["voice", "get", "nonexistent_id"])

            assert result.exit_code != 0 or "error" in result.output.lower() or "not found" in result.output.lower()

    def test_create_agent_validation_error(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test CLI displays validation errors."""
        from httpx import HTTPStatusError

        mock_response = MagicMock(status_code=400)
        mock_response.json.return_value = {"error": "Validation error", "message": "voice_id is required"}
        mock_ghl_client_context.voice_ai.create_agent = AsyncMock(
            side_effect=HTTPStatusError("HTTP 400", request=MagicMock(), response=mock_response)
        )

        with patch("ghl_assistant.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, ["voice", "create", "", ""])

            assert result.exit_code != 0 or "error" in result.output.lower()

    def test_get_transcript_not_found(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test CLI handles 404 when getting non-existent call transcript."""
        from httpx import HTTPStatusError

        mock_ghl_client_context.voice_ai.get_call = AsyncMock(
            side_effect=HTTPStatusError(
                "HTTP 404", request=MagicMock(), response=MagicMock(status_code=404)
            )
        )

        with patch("ghl_assistant.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, ["voice", "transcript", "nonexistent_id"])

            assert result.exit_code != 0 or "error" in result.output.lower() or "not found" in result.output.lower()
