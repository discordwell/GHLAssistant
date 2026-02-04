"""Tests for AI browser automation tasks."""

import pytest
from unittest.mock import MagicMock

from ghl_assistant.browser.chrome_mcp.ai_tasks import AIBrowserTasks
from ghl_assistant.browser.chrome_mcp.tasks import TaskStep


class TestAIBrowserTasks:
    """Test suite for AIBrowserTasks class."""

    @pytest.fixture
    def ai_tasks(self, mock_tab_id):
        """Create AIBrowserTasks instance."""
        return AIBrowserTasks(tab_id=mock_tab_id)

    # =========================================================================
    # Navigation Tests
    # =========================================================================

    def test_navigate_to_automations(self, ai_tasks):
        """Test generating steps for automations navigation."""
        steps = ai_tasks.navigate_to_automations()

        assert len(steps) == 2
        assert all(isinstance(s, TaskStep) for s in steps)

        # First step should navigate
        assert steps[0].name == "navigate_automations"
        assert "navigate" in steps[0].command["tool"]
        assert "automations" in steps[0].command["params"]["url"]

        # Second step should screenshot
        assert steps[1].name == "verify_automations_page"
        assert "screenshot" in steps[1].command["params"]["action"]

    def test_navigate_to_conversation_ai(self, ai_tasks):
        """Test generating steps for Conversation AI navigation."""
        steps = ai_tasks.navigate_to_conversation_ai()

        assert len(steps) == 2
        assert "conversation-ai" in steps[0].command["params"]["url"]

    def test_navigate_to_voice_ai(self, ai_tasks):
        """Test generating steps for Voice AI navigation."""
        steps = ai_tasks.navigate_to_voice_ai()

        assert len(steps) == 2
        assert "voice-ai" in steps[0].command["params"]["url"]

    # =========================================================================
    # Workflow Creation Tests
    # =========================================================================

    def test_create_workflow_for_ai_conversation_trigger(self, ai_tasks):
        """Test creating workflow with conversation AI trigger."""
        steps = ai_tasks.create_workflow_for_ai(
            name="AI Lead Capture",
            trigger="conversation_ai",
        )

        assert len(steps) > 0
        assert all(isinstance(s, TaskStep) for s in steps)

        # Verify workflow name is entered
        name_steps = [s for s in steps if "enter_name" in s.name]
        assert len(name_steps) == 1
        assert "AI Lead Capture" in name_steps[0].description

        # Verify conversation AI trigger is found
        trigger_steps = [s for s in steps if "ai_trigger" in s.name.lower() or "conversation" in s.description.lower()]
        assert len(trigger_steps) >= 1

    def test_create_workflow_for_ai_voice_trigger(self, ai_tasks):
        """Test creating workflow with voice AI trigger."""
        steps = ai_tasks.create_workflow_for_ai(
            name="Voice Response Workflow",
            trigger="voice_ai",
        )

        assert len(steps) > 0

        # Verify voice trigger is found
        trigger_steps = [s for s in steps if "voice_trigger" in s.name.lower() or "voice" in s.description.lower()]
        assert len(trigger_steps) >= 1

    def test_create_workflow_for_ai_manual_trigger(self, ai_tasks):
        """Test creating workflow with manual trigger."""
        steps = ai_tasks.create_workflow_for_ai(
            name="Manual Workflow",
            trigger="manual",
        )

        assert len(steps) > 0

        # Verify manual trigger is found
        trigger_steps = [s for s in steps if "manual_trigger" in s.name.lower() or "manual" in s.description.lower()]
        assert len(trigger_steps) >= 1

    def test_create_workflow_has_save_step(self, ai_tasks):
        """Test that workflow creation includes save step."""
        steps = ai_tasks.create_workflow_for_ai(
            name="Test Workflow",
            trigger="conversation_ai",
        )

        save_steps = [s for s in steps if "save" in s.name.lower()]
        assert len(save_steps) >= 1

    def test_create_workflow_includes_screenshots(self, ai_tasks):
        """Test that workflow creation includes screenshots for debugging."""
        steps = ai_tasks.create_workflow_for_ai(
            name="Test Workflow",
            trigger="conversation_ai",
        )

        screenshot_steps = [s for s in steps if "screenshot" in s.command.get("params", {}).get("action", "")]
        assert len(screenshot_steps) >= 2  # At least initial and final screenshots

    # =========================================================================
    # Agent Connection Tests
    # =========================================================================

    def test_connect_workflow_to_conversation_agent(self, ai_tasks):
        """Test connecting workflow to conversation AI agent."""
        steps = ai_tasks.connect_workflow_to_agent(
            workflow_name="AI Lead Capture",
            agent_name="Support Bot",
            agent_type="conversation",
        )

        assert len(steps) > 0
        assert all(isinstance(s, TaskStep) for s in steps)

        # Verify navigation to AI settings
        nav_steps = [s for s in steps if "conversation-ai" in str(s.command.get("params", {}))]
        assert len(nav_steps) >= 1

        # Verify agent search
        agent_steps = [s for s in steps if "Support Bot" in s.description]
        assert len(agent_steps) >= 1

        # Verify workflow search
        workflow_steps = [s for s in steps if "AI Lead Capture" in s.description]
        assert len(workflow_steps) >= 1

    def test_connect_workflow_to_voice_agent(self, ai_tasks):
        """Test connecting workflow to voice AI agent."""
        steps = ai_tasks.connect_workflow_to_agent(
            workflow_name="Call Handler",
            agent_name="Voice Bot",
            agent_type="voice",
        )

        assert len(steps) > 0

        # Verify navigation to voice AI settings
        nav_steps = [s for s in steps if "voice-ai" in str(s.command.get("params", {}))]
        assert len(nav_steps) >= 1

        # Verify agent search
        agent_steps = [s for s in steps if "Voice Bot" in s.description]
        assert len(agent_steps) >= 1

    def test_connect_workflow_has_save_step(self, ai_tasks):
        """Test that connecting workflow includes save step."""
        steps = ai_tasks.connect_workflow_to_agent(
            workflow_name="Test Workflow",
            agent_name="Test Agent",
            agent_type="conversation",
        )

        save_steps = [s for s in steps if "save" in s.name.lower()]
        assert len(save_steps) >= 1

    # =========================================================================
    # Agent Details Capture Tests
    # =========================================================================

    def test_capture_ai_agent_details(self, ai_tasks):
        """Test capturing AI agent details."""
        steps = ai_tasks.capture_ai_agent_details(agent_name="Support Bot")

        assert len(steps) == 4

        # Verify agent search
        assert "Support Bot" in steps[0].description

        # Verify screenshot capture
        screenshot_steps = [s for s in steps if "screenshot" in s.name.lower()]
        assert len(screenshot_steps) >= 1

        # Verify page read
        read_steps = [s for s in steps if "read_page" in s.command.get("tool", "")]
        assert len(read_steps) >= 1

    # =========================================================================
    # Task Step Properties Tests
    # =========================================================================

    def test_task_steps_have_required_properties(self, ai_tasks):
        """Test that all generated task steps have required properties."""
        steps = ai_tasks.create_workflow_for_ai(
            name="Test",
            trigger="conversation_ai",
        )

        for step in steps:
            assert hasattr(step, "name")
            assert hasattr(step, "description")
            assert hasattr(step, "command")
            assert isinstance(step.command, dict)
            assert "tool" in step.command or "params" in step.command

    def test_task_steps_have_tab_id(self, ai_tasks, mock_tab_id):
        """Test that all task steps include the correct tab ID."""
        steps = ai_tasks.navigate_to_automations()

        for step in steps:
            if "params" in step.command:
                assert step.command["params"].get("tabId") == mock_tab_id

    def test_task_steps_have_wait_times(self, ai_tasks):
        """Test that navigation steps have appropriate wait times."""
        steps = ai_tasks.navigate_to_automations()

        nav_step = steps[0]
        assert nav_step.wait_after >= 1.0  # Navigation should wait for page load


class TestAIBrowserTasksEdgeCases:
    """Edge case tests for AIBrowserTasks."""

    def test_empty_workflow_name(self):
        """Test creating workflow with empty name."""
        tasks = AIBrowserTasks(tab_id=12345)
        steps = tasks.create_workflow_for_ai(name="", trigger="conversation_ai")

        # Should still generate steps (validation is not enforced)
        assert len(steps) > 0

    def test_unknown_trigger_type(self):
        """Test creating workflow with unknown trigger type."""
        tasks = AIBrowserTasks(tab_id=12345)
        steps = tasks.create_workflow_for_ai(name="Test", trigger="unknown")

        # Should fall back to manual trigger
        trigger_steps = [s for s in steps if "manual" in s.description.lower()]
        assert len(trigger_steps) >= 1

    def test_special_characters_in_names(self):
        """Test handling special characters in names."""
        tasks = AIBrowserTasks(tab_id=12345)
        steps = tasks.create_workflow_for_ai(
            name="Test Workflow <script>alert('xss')</script>",
            trigger="conversation_ai",
        )

        # Steps should be generated without error
        assert len(steps) > 0

        # The name should be included as-is (browser will handle escaping)
        name_steps = [s for s in steps if "Test Workflow" in s.description]
        assert len(name_steps) >= 1


class TestTaskStepCommandStructure:
    """Tests for task step command structure compatibility."""

    def test_navigate_command_structure(self):
        """Test navigate command has correct structure for Chrome MCP."""
        tasks = AIBrowserTasks(tab_id=12345)
        steps = tasks.navigate_to_automations()

        nav_command = steps[0].command
        assert nav_command["tool"] == "mcp__claude-in-chrome__navigate"
        assert "url" in nav_command["params"]
        assert "tabId" in nav_command["params"]

    def test_screenshot_command_structure(self):
        """Test screenshot command has correct structure for Chrome MCP."""
        tasks = AIBrowserTasks(tab_id=12345)
        steps = tasks.navigate_to_automations()

        # Find screenshot step
        screenshot_step = steps[1]
        screenshot_command = screenshot_step.command

        assert screenshot_command["tool"] == "mcp__claude-in-chrome__computer"
        assert screenshot_command["params"]["action"] == "screenshot"
        assert "tabId" in screenshot_command["params"]

    def test_find_elements_command_structure(self):
        """Test find elements command has correct structure."""
        tasks = AIBrowserTasks(tab_id=12345)
        steps = tasks.create_workflow_for_ai(name="Test", trigger="conversation_ai")

        # Find a step that uses find
        find_steps = [s for s in steps if "find" in s.command.get("tool", "")]
        assert len(find_steps) > 0

        find_command = find_steps[0].command
        assert find_command["tool"] == "mcp__claude-in-chrome__find"
        assert "query" in find_command["params"]
        assert "tabId" in find_command["params"]

    def test_type_text_command_structure(self):
        """Test type text command has correct structure."""
        tasks = AIBrowserTasks(tab_id=12345)
        steps = tasks.create_workflow_for_ai(name="Test Workflow", trigger="conversation_ai")

        # Find the enter_name step
        type_steps = [s for s in steps if "enter_name" in s.name]
        assert len(type_steps) == 1

        type_command = type_steps[0].command
        assert type_command["tool"] == "mcp__claude-in-chrome__computer"
        assert type_command["params"]["action"] == "type"
        assert type_command["params"]["text"] == "Test Workflow"

    def test_wait_command_structure(self):
        """Test wait command has correct structure."""
        tasks = AIBrowserTasks(tab_id=12345)
        steps = tasks.create_workflow_for_ai(name="Test", trigger="conversation_ai")

        # Find a wait step
        wait_steps = [s for s in steps if "wait" in s.command.get("params", {}).get("action", "")]
        assert len(wait_steps) > 0

        wait_command = wait_steps[0].command
        assert wait_command["tool"] == "mcp__claude-in-chrome__computer"
        assert wait_command["params"]["action"] == "wait"
        assert "duration" in wait_command["params"]
        assert wait_command["params"]["duration"] <= 30  # Max wait time


class TestAIBrowserTasksIntegration:
    """Integration-style tests for AIBrowserTasks workflows."""

    def test_full_workflow_creation_flow(self):
        """Test the complete workflow creation flow."""
        tasks = AIBrowserTasks(tab_id=12345)

        # Step 1: Create workflow
        create_steps = tasks.create_workflow_for_ai(
            name="Full Test Workflow",
            trigger="conversation_ai",
        )

        # Verify the flow makes sense
        step_names = [s.name for s in create_steps]

        # Should navigate first
        assert "navigate_automations" in step_names

        # Should have screenshot for verification
        assert any("screenshot" in name for name in step_names)

        # Should find create button
        assert any("create" in name or "add" in name for name in step_names)

        # Should enter name
        assert "enter_name" in step_names

        # Should find trigger
        assert any("trigger" in name for name in step_names)

        # Should save
        assert any("save" in name for name in step_names)

    def test_full_agent_connection_flow(self):
        """Test the complete agent connection flow."""
        tasks = AIBrowserTasks(tab_id=12345)

        # Connect workflow to agent
        connect_steps = tasks.connect_workflow_to_agent(
            workflow_name="Test Workflow",
            agent_name="Test Agent",
            agent_type="conversation",
        )

        step_names = [s.name for s in connect_steps]

        # Should navigate to AI settings
        assert any("navigate" in name for name in step_names)

        # Should find agent
        assert any("agent" in name for name in step_names)

        # Should find actions section
        assert any("action" in name for name in step_names)

        # Should search for workflow
        assert any("workflow" in name for name in step_names)

        # Should save
        assert any("save" in name for name in step_names)

        # Should verify with screenshot
        assert any("screenshot" in name for name in step_names)
