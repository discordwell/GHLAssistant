"""Tests for the Chrome MCP task executor module."""

import pytest
from unittest.mock import MagicMock, patch
from io import StringIO

from rich.console import Console

from maxlevel.browser.chrome_mcp.executor import (
    ExecutionPlan,
    create_workflow_plan,
    connect_workflow_plan,
    navigate_to_ai_settings_plan,
    capture_agent_details_plan,
)
from maxlevel.browser.chrome_mcp.tasks import TaskStep


class TestExecutionPlan:
    """Tests for ExecutionPlan dataclass."""

    @pytest.fixture
    def sample_steps(self):
        """Create sample TaskSteps for testing."""
        return [
            TaskStep(
                name="step_1",
                description="First step",
                command={"tool": "test", "params": {"action": "test"}},
            ),
            TaskStep(
                name="step_2",
                description="Second step",
                command={"tool": "test2", "params": {"action": "test2"}},
            ),
        ]

    def test_execution_plan_creation(self, sample_steps):
        """Test ExecutionPlan can be created with steps."""
        plan = ExecutionPlan(
            steps=sample_steps,
            description="Test plan",
        )

        assert len(plan.steps) == 2
        assert plan.description == "Test plan"
        assert plan.trigger_type is None
        assert plan.target_name is None

    def test_execution_plan_with_metadata(self, sample_steps):
        """Test ExecutionPlan with optional metadata."""
        plan = ExecutionPlan(
            steps=sample_steps,
            description="Test plan",
            trigger_type="conversation_ai",
            target_name="Test Workflow",
        )

        assert plan.trigger_type == "conversation_ai"
        assert plan.target_name == "Test Workflow"

    def test_to_mcp_commands(self, sample_steps):
        """Test converting steps to MCP command dicts."""
        plan = ExecutionPlan(
            steps=sample_steps,
            description="Test plan",
        )

        commands = plan.to_mcp_commands()

        assert len(commands) == 2
        assert commands[0]["tool"] == "test"
        assert commands[1]["tool"] == "test2"

    def test_print_plan_outputs_table(self, sample_steps):
        """Test that print_plan outputs a formatted table."""
        plan = ExecutionPlan(
            steps=sample_steps,
            description="Test plan",
        )

        # Capture output
        output = StringIO()
        console = Console(file=output, force_terminal=True, width=100)

        plan.print_plan(console)

        output_text = output.getvalue()
        assert "Test plan" in output_text
        assert "step_1" in output_text or "First step" in output_text
        assert "step_2" in output_text or "Second step" in output_text

    def test_print_summary_outputs_panel(self, sample_steps):
        """Test that print_summary outputs a summary panel."""
        plan = ExecutionPlan(
            steps=sample_steps,
            description="Test plan",
            trigger_type="conversation_ai",
            target_name="Test Workflow",
        )

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=100)

        plan.print_summary(console)

        output_text = output.getvalue()
        assert "Test plan" in output_text
        assert "Steps: 2" in output_text


class TestCreateWorkflowPlan:
    """Tests for create_workflow_plan function."""

    def test_create_workflow_plan_basic(self):
        """Test creating a basic workflow plan."""
        plan = create_workflow_plan(
            tab_id=12345,
            name="Test Workflow",
            trigger="manual",
        )

        assert isinstance(plan, ExecutionPlan)
        assert len(plan.steps) > 0
        assert "Test Workflow" in plan.description
        assert plan.target_name == "Test Workflow"
        assert plan.trigger_type == "manual"

    def test_create_workflow_plan_conversation_ai_trigger(self):
        """Test creating workflow with conversation AI trigger."""
        plan = create_workflow_plan(
            tab_id=12345,
            name="AI Workflow",
            trigger="conversation_ai",
        )

        assert "Conversation AI" in plan.description
        assert plan.trigger_type == "conversation_ai"

    def test_create_workflow_plan_voice_ai_trigger(self):
        """Test creating workflow with voice AI trigger."""
        plan = create_workflow_plan(
            tab_id=12345,
            name="Voice Workflow",
            trigger="voice_ai",
        )

        assert "Voice AI" in plan.description
        assert plan.trigger_type == "voice_ai"

    def test_create_workflow_plan_includes_navigation(self):
        """Test that plan includes navigation step."""
        plan = create_workflow_plan(
            tab_id=12345,
            name="Test",
            trigger="manual",
        )

        step_names = [s.name for s in plan.steps]
        assert any("navigate" in name for name in step_names)

    def test_create_workflow_plan_includes_save(self):
        """Test that plan includes save step."""
        plan = create_workflow_plan(
            tab_id=12345,
            name="Test",
            trigger="manual",
        )

        step_names = [s.name for s in plan.steps]
        assert any("save" in name for name in step_names)


class TestConnectWorkflowPlan:
    """Tests for connect_workflow_plan function."""

    def test_connect_workflow_plan_basic(self):
        """Test creating a basic connect workflow plan."""
        plan = connect_workflow_plan(
            tab_id=12345,
            workflow_name="Test Workflow",
            agent_name="Test Agent",
            agent_type="conversation",
        )

        assert isinstance(plan, ExecutionPlan)
        assert len(plan.steps) > 0
        assert "Test Workflow" in plan.description
        assert "Test Agent" in plan.description
        assert plan.target_name == "Test Workflow"
        assert plan.trigger_type == "conversation"

    def test_connect_workflow_plan_conversation_type(self):
        """Test connecting to conversation AI agent."""
        plan = connect_workflow_plan(
            tab_id=12345,
            workflow_name="Workflow",
            agent_name="Agent",
            agent_type="conversation",
        )

        assert "Conversation AI" in plan.description

    def test_connect_workflow_plan_voice_type(self):
        """Test connecting to voice AI agent."""
        plan = connect_workflow_plan(
            tab_id=12345,
            workflow_name="Workflow",
            agent_name="Agent",
            agent_type="voice",
        )

        assert "Voice AI" in plan.description

    def test_connect_workflow_plan_includes_navigation(self):
        """Test that plan includes navigation to AI settings."""
        plan = connect_workflow_plan(
            tab_id=12345,
            workflow_name="Workflow",
            agent_name="Agent",
            agent_type="conversation",
        )

        step_names = [s.name for s in plan.steps]
        assert any("navigate" in name for name in step_names)

    def test_connect_workflow_plan_includes_agent_search(self):
        """Test that plan includes agent search step."""
        plan = connect_workflow_plan(
            tab_id=12345,
            workflow_name="Workflow",
            agent_name="Agent",
            agent_type="conversation",
        )

        step_descriptions = [s.description for s in plan.steps]
        assert any("Agent" in desc for desc in step_descriptions)


class TestNavigateToAISettingsPlan:
    """Tests for navigate_to_ai_settings_plan function."""

    def test_navigate_to_conversation_ai(self):
        """Test navigating to conversation AI settings."""
        plan = navigate_to_ai_settings_plan(
            tab_id=12345,
            ai_type="conversation",
        )

        assert isinstance(plan, ExecutionPlan)
        assert "Conversation AI" in plan.description
        assert plan.trigger_type == "conversation"

    def test_navigate_to_voice_ai(self):
        """Test navigating to voice AI settings."""
        plan = navigate_to_ai_settings_plan(
            tab_id=12345,
            ai_type="voice",
        )

        assert isinstance(plan, ExecutionPlan)
        assert "Voice AI" in plan.description
        assert plan.trigger_type == "voice"

    def test_navigate_plan_has_minimal_steps(self):
        """Test that navigation plan has few steps."""
        plan = navigate_to_ai_settings_plan(
            tab_id=12345,
            ai_type="conversation",
        )

        # Navigation should be simple: navigate + verify
        assert len(plan.steps) <= 3


class TestCaptureAgentDetailsPlan:
    """Tests for capture_agent_details_plan function."""

    def test_capture_agent_details_basic(self):
        """Test capturing agent details."""
        plan = capture_agent_details_plan(
            tab_id=12345,
            agent_name="Support Bot",
        )

        assert isinstance(plan, ExecutionPlan)
        assert "Support Bot" in plan.description
        assert plan.target_name == "Support Bot"

    def test_capture_agent_details_includes_screenshot(self):
        """Test that capture plan includes screenshot."""
        plan = capture_agent_details_plan(
            tab_id=12345,
            agent_name="Bot",
        )

        step_names = [s.name for s in plan.steps]
        assert any("screenshot" in name for name in step_names)

    def test_capture_agent_details_includes_page_read(self):
        """Test that capture plan includes page read."""
        plan = capture_agent_details_plan(
            tab_id=12345,
            agent_name="Bot",
        )

        step_names = [s.name for s in plan.steps]
        assert any("read" in name for name in step_names)


class TestExecutionPlanMCPCompatibility:
    """Tests for MCP command compatibility."""

    def test_all_steps_have_valid_mcp_structure(self):
        """Test that all generated steps have valid MCP command structure."""
        plan = create_workflow_plan(
            tab_id=12345,
            name="Test",
            trigger="conversation_ai",
        )

        for step in plan.steps:
            assert isinstance(step.command, dict)
            # Should have either 'tool' key or be structured for MCP
            assert "tool" in step.command or "params" in step.command

    def test_tab_id_propagates_to_commands(self):
        """Test that tab_id is included in command params."""
        plan = create_workflow_plan(
            tab_id=99999,
            name="Test",
            trigger="manual",
        )

        commands = plan.to_mcp_commands()
        for cmd in commands:
            if "params" in cmd:
                assert cmd["params"].get("tabId") == 99999
