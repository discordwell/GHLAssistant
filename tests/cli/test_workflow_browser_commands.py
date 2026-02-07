"""Tests for workflow browser automation CLI commands."""

import pytest
from typer.testing import CliRunner

from maxlevel.cli import app


class TestWorkflowsCreateForAICommand:
    """Tests for 'maxlevel workflows create-for-ai' command."""

    def test_create_for_ai_dry_run(self, cli_runner):
        """Test dry run shows plan without executing."""
        result = cli_runner.invoke(
            app,
            ["workflows", "create-for-ai", "Test Workflow", "--dry-run"],
        )

        assert result.exit_code == 0
        assert "Test Workflow" in result.output
        assert "Dry run" in result.output
        assert "no actions taken" in result.output.lower()

    def test_create_for_ai_with_conversation_trigger(self, cli_runner):
        """Test creating workflow with conversation AI trigger."""
        result = cli_runner.invoke(
            app,
            [
                "workflows",
                "create-for-ai",
                "AI Lead Capture",
                "--trigger",
                "conversation_ai",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        assert "AI Lead Capture" in result.output
        assert "Conversation AI" in result.output

    def test_create_for_ai_with_voice_trigger(self, cli_runner):
        """Test creating workflow with voice AI trigger."""
        result = cli_runner.invoke(
            app,
            [
                "workflows",
                "create-for-ai",
                "Voice Response",
                "-t",
                "voice_ai",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        assert "Voice Response" in result.output
        assert "Voice AI" in result.output

    def test_create_for_ai_with_manual_trigger(self, cli_runner):
        """Test creating workflow with manual trigger."""
        result = cli_runner.invoke(
            app,
            [
                "workflows",
                "create-for-ai",
                "Manual Workflow",
                "--trigger",
                "manual",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        assert "Manual Workflow" in result.output
        assert "Manual" in result.output

    def test_create_for_ai_shows_steps_table(self, cli_runner):
        """Test that dry run shows a steps table."""
        result = cli_runner.invoke(
            app,
            ["workflows", "create-for-ai", "Test", "--dry-run"],
        )

        assert result.exit_code == 0
        # Check for table structure indicators
        assert "Step" in result.output or "#" in result.output
        assert "navigate" in result.output.lower()

    def test_create_for_ai_without_dry_run_shows_instructions(self, cli_runner):
        """Test that running without dry-run shows execution instructions."""
        result = cli_runner.invoke(
            app,
            ["workflows", "create-for-ai", "Test Workflow"],
        )

        assert result.exit_code == 0
        assert "Chrome" in result.output
        assert "Claude-in-Chrome" in result.output or "browser" in result.output.lower()

    def test_create_for_ai_help(self, cli_runner):
        """Test help output for create-for-ai command."""
        result = cli_runner.invoke(app, ["workflows", "create-for-ai", "--help"])

        assert result.exit_code == 0
        assert "Create a workflow" in result.output
        assert "--trigger" in result.output
        assert "--dry-run" in result.output


class TestWorkflowsConnectAICommand:
    """Tests for 'maxlevel workflows connect-ai' command."""

    def test_connect_ai_dry_run(self, cli_runner):
        """Test dry run shows plan without executing."""
        result = cli_runner.invoke(
            app,
            [
                "workflows",
                "connect-ai",
                "Test Workflow",
                "Support Bot",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        assert "Test Workflow" in result.output
        assert "Support Bot" in result.output
        assert "Dry run" in result.output

    def test_connect_ai_conversation_type(self, cli_runner):
        """Test connecting to conversation AI agent."""
        result = cli_runner.invoke(
            app,
            [
                "workflows",
                "connect-ai",
                "Lead Workflow",
                "Chat Bot",
                "--type",
                "conversation",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        assert "Conversation AI" in result.output

    def test_connect_ai_voice_type(self, cli_runner):
        """Test connecting to voice AI agent."""
        result = cli_runner.invoke(
            app,
            [
                "workflows",
                "connect-ai",
                "Call Workflow",
                "Voice Agent",
                "-t",
                "voice",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        assert "Voice AI" in result.output

    def test_connect_ai_shows_steps_table(self, cli_runner):
        """Test that dry run shows a steps table."""
        result = cli_runner.invoke(
            app,
            [
                "workflows",
                "connect-ai",
                "Workflow",
                "Agent",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        # Should show navigation, find agent, connect workflow steps
        assert "navigate" in result.output.lower()

    def test_connect_ai_without_dry_run_shows_instructions(self, cli_runner):
        """Test that running without dry-run shows execution instructions."""
        result = cli_runner.invoke(
            app,
            ["workflows", "connect-ai", "Workflow", "Agent"],
        )

        assert result.exit_code == 0
        assert "Chrome" in result.output
        assert "Claude-in-Chrome" in result.output or "browser" in result.output.lower()

    def test_connect_ai_help(self, cli_runner):
        """Test help output for connect-ai command."""
        result = cli_runner.invoke(app, ["workflows", "connect-ai", "--help"])

        assert result.exit_code == 0
        assert "Connect a workflow" in result.output
        assert "--type" in result.output
        assert "--dry-run" in result.output

    def test_connect_ai_requires_workflow_name(self, cli_runner):
        """Test that workflow name is required."""
        result = cli_runner.invoke(app, ["workflows", "connect-ai"])

        # Should fail with missing argument error
        assert result.exit_code != 0

    def test_connect_ai_requires_agent_name(self, cli_runner):
        """Test that agent name is required."""
        result = cli_runner.invoke(app, ["workflows", "connect-ai", "Workflow"])

        # Should fail with missing argument error
        assert result.exit_code != 0


class TestWorkflowBrowserCommandsIntegration:
    """Integration tests for workflow browser commands."""

    def test_commands_are_registered(self, cli_runner):
        """Test that both commands are registered in workflows group."""
        result = cli_runner.invoke(app, ["workflows", "--help"])

        assert result.exit_code == 0
        assert "create-for-ai" in result.output
        assert "connect-ai" in result.output

    def test_create_and_connect_workflow_plan_compatibility(self, cli_runner):
        """Test that create and connect commands produce compatible plans."""
        # Create workflow
        create_result = cli_runner.invoke(
            app,
            [
                "workflows",
                "create-for-ai",
                "AI Integration Workflow",
                "--trigger",
                "conversation_ai",
                "--dry-run",
            ],
        )
        assert create_result.exit_code == 0

        # Connect workflow
        connect_result = cli_runner.invoke(
            app,
            [
                "workflows",
                "connect-ai",
                "AI Integration Workflow",
                "Support Bot",
                "--type",
                "conversation",
                "--dry-run",
            ],
        )
        assert connect_result.exit_code == 0

        # Both should reference the workflow name
        assert "AI Integration Workflow" in create_result.output
        assert "AI Integration Workflow" in connect_result.output
