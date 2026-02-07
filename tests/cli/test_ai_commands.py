"""Tests for Conversation AI CLI commands."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from typer.testing import CliRunner

from maxlevel.cli import app
from tests.conftest import (
    SAMPLE_AGENT_ID,
    SAMPLE_ACTION_ID,
    SAMPLE_WORKFLOW_ID,
    MOCK_CONVERSATION_AI_AGENT,
    MOCK_ACTION,
    MOCK_GENERATION,
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


class TestAIListCommand:
    """Tests for 'maxlevel ai list' command."""

    def test_list_agents(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test listing conversation AI agents."""
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, ["ai", "list"])

            assert result.exit_code == 0
            assert "Conversation AI Agents" in result.output
            assert "Test Bot" in result.output
            mock_ghl_client_context.conversation_ai.list_agents.assert_called_with(limit=50)

    def test_list_agents_json(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test listing agents with JSON output."""
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, ["ai", "list", "--json"])

            assert result.exit_code == 0
            assert '"agents"' in result.output
            mock_ghl_client_context.conversation_ai.list_agents.assert_called_with(limit=50)

    def test_list_agents_with_limit(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test listing agents with custom limit."""
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, ["ai", "list", "--limit", "10"])

            assert result.exit_code == 0
            mock_ghl_client_context.conversation_ai.list_agents.assert_called_with(limit=10)


class TestAIGetCommand:
    """Tests for 'maxlevel ai get' command."""

    def test_get_agent(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test getting a single agent."""
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, ["ai", "get", SAMPLE_AGENT_ID])

            assert result.exit_code == 0
            mock_ghl_client_context.conversation_ai.get_agent.assert_called_with(SAMPLE_AGENT_ID)
            # Verify output contains agent data
            assert "Test Bot" in result.output or SAMPLE_AGENT_ID in result.output


class TestAICreateCommand:
    """Tests for 'maxlevel ai create' command."""

    def test_create_agent_minimal(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test creating an agent with minimal parameters."""
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, ["ai", "create", "Test Bot"])

            assert result.exit_code == 0
            assert "created" in result.output.lower()
            # CLI passes all parameters including defaults
            mock_ghl_client_context.conversation_ai.create_agent.assert_called_with(
                name="Test Bot",
                prompt=None,
                model="gpt-4",
                temperature=0.7,
            )

    def test_create_agent_full(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test creating an agent with all parameters."""
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, [
                "ai", "create", "Full Bot",
                "--prompt", "You are helpful.",
                "--model", "gpt-3.5-turbo",
                "--temperature", "0.5",
            ])

            assert result.exit_code == 0
            mock_ghl_client_context.conversation_ai.create_agent.assert_called_with(
                name="Full Bot",
                prompt="You are helpful.",
                model="gpt-3.5-turbo",
                temperature=0.5,
            )


class TestAIUpdateCommand:
    """Tests for 'maxlevel ai update' command."""

    def test_update_agent(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test updating an agent."""
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, [
                "ai", "update", SAMPLE_AGENT_ID,
                "--name", "Updated Bot",
                "--temperature", "0.9",
            ])

            assert result.exit_code == 0
            assert "updated" in result.output.lower()
            # CLI passes all parameters including None for unspecified options
            mock_ghl_client_context.conversation_ai.update_agent.assert_called_with(
                SAMPLE_AGENT_ID,
                name="Updated Bot",
                prompt=None,
                model=None,
                temperature=0.9,
                enabled=None,
            )

    def test_update_agent_enable(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test enabling an agent."""
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, [
                "ai", "update", SAMPLE_AGENT_ID, "--enabled",
            ])

            assert result.exit_code == 0
            mock_ghl_client_context.conversation_ai.update_agent.assert_called_with(
                SAMPLE_AGENT_ID,
                name=None,
                prompt=None,
                model=None,
                temperature=None,
                enabled=True,
            )

    def test_update_agent_disable(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test disabling an agent."""
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, [
                "ai", "update", SAMPLE_AGENT_ID, "--disabled",
            ])

            assert result.exit_code == 0
            mock_ghl_client_context.conversation_ai.update_agent.assert_called_with(
                SAMPLE_AGENT_ID,
                name=None,
                prompt=None,
                model=None,
                temperature=None,
                enabled=False,
            )


class TestAIDeleteCommand:
    """Tests for 'maxlevel ai delete' command."""

    def test_delete_agent_with_confirmation(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test deleting an agent with confirmation."""
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, ["ai", "delete", SAMPLE_AGENT_ID], input="y\n")

            assert result.exit_code == 0
            assert "deleted" in result.output.lower()

    def test_delete_agent_skip_confirmation(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test deleting an agent with --yes flag."""
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, ["ai", "delete", SAMPLE_AGENT_ID, "--yes"])

            assert result.exit_code == 0
            assert "deleted" in result.output.lower()

    def test_delete_agent_abort(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test aborting agent deletion."""
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, ["ai", "delete", SAMPLE_AGENT_ID], input="n\n")

            assert result.exit_code == 0
            assert "aborted" in result.output.lower()


class TestAIActionsCommand:
    """Tests for 'maxlevel ai actions' command."""

    def test_list_actions(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test listing agent actions."""
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, ["ai", "actions", SAMPLE_AGENT_ID])

            assert result.exit_code == 0
            assert "Agent Actions" in result.output
            mock_ghl_client_context.conversation_ai.list_actions.assert_called_with(SAMPLE_AGENT_ID)


class TestAIAttachActionCommand:
    """Tests for 'maxlevel ai attach-action' command."""

    def test_attach_action(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test attaching an action to an agent."""
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, [
                "ai", "attach-action", SAMPLE_AGENT_ID, SAMPLE_WORKFLOW_ID,
            ])

            assert result.exit_code == 0
            assert "attached" in result.output.lower()
            mock_ghl_client_context.conversation_ai.attach_action.assert_called_with(
                SAMPLE_AGENT_ID,
                SAMPLE_WORKFLOW_ID,
                action_type="workflow",
                trigger_condition=None,
            )

    def test_attach_action_with_trigger(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test attaching an action with trigger condition."""
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, [
                "ai", "attach-action", SAMPLE_AGENT_ID, SAMPLE_WORKFLOW_ID,
                "--trigger", "intent:book_appointment",
            ])

            assert result.exit_code == 0
            mock_ghl_client_context.conversation_ai.attach_action.assert_called_with(
                SAMPLE_AGENT_ID,
                SAMPLE_WORKFLOW_ID,
                action_type="workflow",
                trigger_condition="intent:book_appointment",
            )


class TestAIRemoveActionCommand:
    """Tests for 'maxlevel ai remove-action' command."""

    def test_remove_action(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test removing an action from an agent."""
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, [
                "ai", "remove-action", SAMPLE_AGENT_ID, SAMPLE_ACTION_ID,
            ])

            assert result.exit_code == 0
            assert "removed" in result.output.lower()
            mock_ghl_client_context.conversation_ai.remove_action.assert_called_with(
                SAMPLE_AGENT_ID,
                SAMPLE_ACTION_ID,
            )


class TestAIHistoryCommand:
    """Tests for 'maxlevel ai history' command."""

    def test_list_history(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test listing AI generation history."""
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, ["ai", "history"])

            assert result.exit_code == 0
            assert "AI Generations" in result.output
            mock_ghl_client_context.conversation_ai.list_generations.assert_called_with(
                agent_id=None,
                contact_id=None,
                limit=50,
            )

    def test_list_history_with_agent_filter(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test filtering history by agent."""
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, [
                "ai", "history", "--agent", SAMPLE_AGENT_ID,
            ])

            assert result.exit_code == 0
            mock_ghl_client_context.conversation_ai.list_generations.assert_called_with(
                agent_id=SAMPLE_AGENT_ID,
                contact_id=None,
                limit=50,
            )


class TestAISettingsCommand:
    """Tests for 'maxlevel ai settings' command."""

    def test_get_settings(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test getting AI settings."""
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, ["ai", "settings"])

            assert result.exit_code == 0
            mock_ghl_client_context.conversation_ai.get_settings.assert_called_once()
            # Verify output displays settings info
            assert "gpt-4" in result.output or "enabled" in result.output.lower()


class TestAICommandHelp:
    """Tests for AI command help output."""

    def test_ai_help(self, cli_runner):
        """Test 'maxlevel ai --help' shows all commands."""
        result = cli_runner.invoke(app, ["ai", "--help"])

        assert result.exit_code == 0
        assert "list" in result.output
        assert "get" in result.output
        assert "create" in result.output
        assert "update" in result.output
        assert "delete" in result.output
        assert "actions" in result.output
        assert "attach-action" in result.output
        assert "remove-action" in result.output
        assert "history" in result.output
        assert "settings" in result.output

    def test_ai_create_help(self, cli_runner):
        """Test 'maxlevel ai create --help' shows options."""
        result = cli_runner.invoke(app, ["ai", "create", "--help"])

        assert result.exit_code == 0
        assert "--prompt" in result.output
        assert "--model" in result.output
        assert "--temperature" in result.output


class TestAICommandErrors:
    """Tests for AI command error handling."""

    def test_list_agents_api_error(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test CLI handles API errors gracefully."""
        from httpx import HTTPStatusError

        mock_ghl_client_context.conversation_ai.list_agents = AsyncMock(
            side_effect=HTTPStatusError(
                "HTTP 500", request=MagicMock(), response=MagicMock(status_code=500)
            )
        )

        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, ["ai", "list"])

            # Should handle error gracefully (non-zero exit or error message)
            assert result.exit_code != 0 or "error" in result.output.lower()

    def test_get_agent_not_found(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test CLI handles 404 error for non-existent agent."""
        from httpx import HTTPStatusError

        mock_ghl_client_context.conversation_ai.get_agent = AsyncMock(
            side_effect=HTTPStatusError(
                "HTTP 404", request=MagicMock(), response=MagicMock(status_code=404)
            )
        )

        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, ["ai", "get", "nonexistent_id"])

            assert result.exit_code != 0 or "error" in result.output.lower() or "not found" in result.output.lower()

    def test_create_agent_validation_error(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test CLI displays validation errors."""
        from httpx import HTTPStatusError

        mock_response = MagicMock(status_code=400)
        mock_response.json.return_value = {"error": "Validation error", "message": "Name is required"}
        mock_ghl_client_context.conversation_ai.create_agent = AsyncMock(
            side_effect=HTTPStatusError("HTTP 400", request=MagicMock(), response=mock_response)
        )

        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, ["ai", "create", ""])

            assert result.exit_code != 0 or "error" in result.output.lower()

    def test_delete_agent_not_found(self, cli_runner, mock_ghl_client_context, mock_client_factory):
        """Test CLI handles 404 on delete."""
        from httpx import HTTPStatusError

        mock_ghl_client_context.conversation_ai.delete_agent = AsyncMock(
            side_effect=HTTPStatusError(
                "HTTP 404", request=MagicMock(), response=MagicMock(status_code=404)
            )
        )

        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = mock_client_factory()

            result = cli_runner.invoke(app, ["ai", "delete", "nonexistent_id", "--yes"])

            assert result.exit_code != 0 or "error" in result.output.lower() or "not found" in result.output.lower()
