"""AI-specific browser automation tasks for GHL.

This module provides browser automation tasks for AI-related operations
that don't have API support, particularly workflow creation for AI agents.

GHL has confirmed there is no API for workflow creation - it's a community
feature request with no ETA. This module provides browser-based fallback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .agent import ChromeMCPAgent
from .tasks import TaskStep, TaskResult


class AIBrowserTasks:
    """AI-specific browser automation tasks for GHL.

    This class provides task definitions for AI-related operations that
    require browser automation due to lack of API support.

    Usage:
        tasks = AIBrowserTasks(tab_id=123)

        # Create a workflow for AI agent
        steps = tasks.create_workflow_for_ai(
            name="AI Lead Capture",
            trigger="conversation_ai",
        )

        # Connect workflow to an AI agent
        steps = tasks.connect_workflow_to_agent(
            workflow_name="AI Lead Capture",
            agent_name="Support Bot",
        )
    """

    GHL_BASE_URL = "https://app.gohighlevel.com"

    def __init__(self, tab_id: int):
        """Initialize with Chrome MCP tab ID.

        Args:
            tab_id: Tab ID from tabs_context_mcp
        """
        self.tab_id = tab_id
        self.agent = ChromeMCPAgent(tab_id)

    # =========================================================================
    # Workflow Creation Tasks
    # =========================================================================

    def navigate_to_automations(self) -> list[TaskStep]:
        """Generate steps to navigate to automations/workflows page.

        Returns:
            List of TaskSteps to navigate to automations
        """
        return [
            TaskStep(
                name="navigate_automations",
                description="Navigate to automations page",
                command=self.agent.navigate(f"{self.GHL_BASE_URL}/automations"),
                wait_after=2.0,
            ),
            TaskStep(
                name="verify_automations_page",
                description="Verify automations page loaded",
                command=self.agent.screenshot(),
            ),
        ]

    def create_workflow_for_ai(
        self,
        name: str,
        trigger: str = "conversation_ai",
    ) -> list[TaskStep]:
        """Generate steps to create a workflow for AI agent triggers.

        Since there's no API for workflow creation, this uses browser automation
        to create workflows through the GHL UI.

        Args:
            name: Workflow name
            trigger: Trigger type ("conversation_ai", "voice_ai", "manual")

        Returns:
            List of TaskSteps to create the workflow
        """
        steps = [
            # Navigate to automations
            TaskStep(
                name="navigate_automations",
                description="Navigate to automations page",
                command=self.agent.navigate(f"{self.GHL_BASE_URL}/automations"),
                wait_after=3.0,
            ),
            TaskStep(
                name="screenshot_automations",
                description="Capture automations page",
                command=self.agent.screenshot(),
            ),
            # Find and click create workflow button
            TaskStep(
                name="find_create_button",
                description="Find create workflow button",
                command=self.agent.find_elements("create workflow button or add new workflow"),
            ),
            TaskStep(
                name="wait_for_modal",
                description="Wait for workflow creation modal",
                command=self.agent.wait(1.5),
            ),
            TaskStep(
                name="screenshot_modal",
                description="Capture workflow creation modal",
                command=self.agent.screenshot(),
            ),
            # Choose to start from scratch
            TaskStep(
                name="find_scratch_option",
                description="Find 'Start from scratch' option",
                command=self.agent.find_elements("start from scratch or blank workflow"),
            ),
            TaskStep(
                name="wait_for_builder",
                description="Wait for workflow builder to load",
                command=self.agent.wait(2.0),
            ),
            TaskStep(
                name="screenshot_builder",
                description="Capture workflow builder",
                command=self.agent.screenshot(),
            ),
            # Set workflow name
            TaskStep(
                name="find_name_field",
                description="Find workflow name field",
                command=self.agent.find_elements("workflow name input or untitled workflow"),
            ),
            TaskStep(
                name="clear_name",
                description="Clear existing name",
                command=self.agent.press_key("cmd+a"),
            ),
            TaskStep(
                name="enter_name",
                description=f"Enter workflow name: {name}",
                command=self.agent.type_text(name),
                wait_after=0.5,
            ),
        ]

        # Add trigger configuration based on type
        if trigger == "conversation_ai":
            steps.extend(self._add_conversation_ai_trigger())
        elif trigger == "voice_ai":
            steps.extend(self._add_voice_ai_trigger())
        else:
            steps.extend(self._add_manual_trigger())

        # Save workflow
        steps.extend([
            TaskStep(
                name="find_save_button",
                description="Find save/publish workflow button",
                command=self.agent.find_elements("save workflow button or publish"),
            ),
            TaskStep(
                name="wait_for_save",
                description="Wait for workflow to save",
                command=self.agent.wait(2.0),
            ),
            TaskStep(
                name="screenshot_saved",
                description="Capture saved workflow",
                command=self.agent.screenshot(),
            ),
        ])

        return steps

    def _add_conversation_ai_trigger(self) -> list[TaskStep]:
        """Generate steps to add Conversation AI trigger to workflow."""
        return [
            TaskStep(
                name="find_trigger_block",
                description="Find add trigger block",
                command=self.agent.find_elements("add trigger or trigger placeholder"),
            ),
            TaskStep(
                name="wait_trigger_menu",
                description="Wait for trigger menu",
                command=self.agent.wait(1.0),
            ),
            TaskStep(
                name="screenshot_triggers",
                description="Capture available triggers",
                command=self.agent.screenshot(),
            ),
            TaskStep(
                name="find_ai_trigger",
                description="Find Conversation AI or AI Response trigger",
                command=self.agent.find_elements("conversation AI trigger or AI response or bot response"),
            ),
            TaskStep(
                name="wait_trigger_config",
                description="Wait for trigger configuration",
                command=self.agent.wait(1.0),
            ),
            TaskStep(
                name="screenshot_trigger_config",
                description="Capture trigger configuration",
                command=self.agent.screenshot(),
            ),
        ]

    def _add_voice_ai_trigger(self) -> list[TaskStep]:
        """Generate steps to add Voice AI trigger to workflow."""
        return [
            TaskStep(
                name="find_trigger_block",
                description="Find add trigger block",
                command=self.agent.find_elements("add trigger or trigger placeholder"),
            ),
            TaskStep(
                name="wait_trigger_menu",
                description="Wait for trigger menu",
                command=self.agent.wait(1.0),
            ),
            TaskStep(
                name="screenshot_triggers",
                description="Capture available triggers",
                command=self.agent.screenshot(),
            ),
            TaskStep(
                name="find_voice_trigger",
                description="Find Voice AI or Call trigger",
                command=self.agent.find_elements("voice AI trigger or call completed or call action"),
            ),
            TaskStep(
                name="wait_trigger_config",
                description="Wait for trigger configuration",
                command=self.agent.wait(1.0),
            ),
            TaskStep(
                name="screenshot_trigger_config",
                description="Capture trigger configuration",
                command=self.agent.screenshot(),
            ),
        ]

    def _add_manual_trigger(self) -> list[TaskStep]:
        """Generate steps to add manual/API trigger to workflow."""
        return [
            TaskStep(
                name="find_trigger_block",
                description="Find add trigger block",
                command=self.agent.find_elements("add trigger or trigger placeholder"),
            ),
            TaskStep(
                name="wait_trigger_menu",
                description="Wait for trigger menu",
                command=self.agent.wait(1.0),
            ),
            TaskStep(
                name="screenshot_triggers",
                description="Capture available triggers",
                command=self.agent.screenshot(),
            ),
            TaskStep(
                name="find_manual_trigger",
                description="Find manual or contact added trigger",
                command=self.agent.find_elements("manual trigger or contact added or workflow trigger"),
            ),
            TaskStep(
                name="wait_trigger_config",
                description="Wait for trigger configuration",
                command=self.agent.wait(1.0),
            ),
            TaskStep(
                name="screenshot_trigger_config",
                description="Capture trigger configuration",
                command=self.agent.screenshot(),
            ),
        ]

    # =========================================================================
    # AI Agent Connection Tasks
    # =========================================================================

    def connect_workflow_to_agent(
        self,
        workflow_name: str,
        agent_name: str,
        agent_type: str = "conversation",
    ) -> list[TaskStep]:
        """Generate steps to connect a workflow to an AI agent.

        Args:
            workflow_name: Name of the workflow to connect
            agent_name: Name of the AI agent
            agent_type: "conversation" or "voice"

        Returns:
            List of TaskSteps to connect workflow to agent
        """
        if agent_type == "conversation":
            return self._connect_to_conversation_ai(workflow_name, agent_name)
        else:
            return self._connect_to_voice_ai(workflow_name, agent_name)

    def _connect_to_conversation_ai(
        self,
        workflow_name: str,
        agent_name: str,
    ) -> list[TaskStep]:
        """Connect workflow to Conversation AI agent."""
        return [
            # Navigate to AI settings
            TaskStep(
                name="navigate_ai_settings",
                description="Navigate to Conversation AI settings",
                command=self.agent.navigate(f"{self.GHL_BASE_URL}/settings/conversation-ai"),
                wait_after=2.0,
            ),
            TaskStep(
                name="screenshot_ai_page",
                description="Capture AI settings page",
                command=self.agent.screenshot(),
            ),
            # Find and select the agent
            TaskStep(
                name="find_agent",
                description=f"Find agent: {agent_name}",
                command=self.agent.find_elements(f"agent named {agent_name} or {agent_name} bot"),
            ),
            TaskStep(
                name="wait_agent_settings",
                description="Wait for agent settings to load",
                command=self.agent.wait(1.5),
            ),
            TaskStep(
                name="screenshot_agent",
                description="Capture agent settings",
                command=self.agent.screenshot(),
            ),
            # Find actions/workflows section
            TaskStep(
                name="find_actions_section",
                description="Find actions or workflows section",
                command=self.agent.find_elements("actions tab or workflows section or add action"),
            ),
            TaskStep(
                name="wait_actions_load",
                description="Wait for actions to load",
                command=self.agent.wait(1.0),
            ),
            TaskStep(
                name="screenshot_actions",
                description="Capture actions section",
                command=self.agent.screenshot(),
            ),
            # Add workflow action
            TaskStep(
                name="find_add_action",
                description="Find add action button",
                command=self.agent.find_elements("add action button or add workflow"),
            ),
            TaskStep(
                name="wait_action_modal",
                description="Wait for action modal",
                command=self.agent.wait(1.0),
            ),
            TaskStep(
                name="screenshot_modal",
                description="Capture action modal",
                command=self.agent.screenshot(),
            ),
            # Search for workflow
            TaskStep(
                name="find_workflow_search",
                description="Find workflow search or dropdown",
                command=self.agent.find_elements("workflow dropdown or search workflows"),
            ),
            TaskStep(
                name="search_workflow",
                description=f"Search for workflow: {workflow_name}",
                command=self.agent.type_text(workflow_name),
                wait_after=1.0,
            ),
            TaskStep(
                name="select_workflow",
                description=f"Select workflow: {workflow_name}",
                command=self.agent.find_elements(f"workflow option {workflow_name}"),
            ),
            # Save
            TaskStep(
                name="find_save",
                description="Find save button",
                command=self.agent.find_elements("save button or confirm"),
            ),
            TaskStep(
                name="wait_save",
                description="Wait for save",
                command=self.agent.wait(1.5),
            ),
            TaskStep(
                name="screenshot_complete",
                description="Capture completed configuration",
                command=self.agent.screenshot(),
            ),
        ]

    def _connect_to_voice_ai(
        self,
        workflow_name: str,
        agent_name: str,
    ) -> list[TaskStep]:
        """Connect workflow to Voice AI agent."""
        return [
            # Navigate to Voice AI settings
            TaskStep(
                name="navigate_voice_settings",
                description="Navigate to Voice AI settings",
                command=self.agent.navigate(f"{self.GHL_BASE_URL}/settings/voice-ai"),
                wait_after=2.0,
            ),
            TaskStep(
                name="screenshot_voice_page",
                description="Capture Voice AI settings page",
                command=self.agent.screenshot(),
            ),
            # Find and select the agent
            TaskStep(
                name="find_agent",
                description=f"Find agent: {agent_name}",
                command=self.agent.find_elements(f"agent named {agent_name} or {agent_name} voice"),
            ),
            TaskStep(
                name="wait_agent_settings",
                description="Wait for agent settings to load",
                command=self.agent.wait(1.5),
            ),
            TaskStep(
                name="screenshot_agent",
                description="Capture agent settings",
                command=self.agent.screenshot(),
            ),
            # Find actions section
            TaskStep(
                name="find_actions_section",
                description="Find actions or workflows section",
                command=self.agent.find_elements("actions tab or workflows section or add action"),
            ),
            TaskStep(
                name="wait_actions_load",
                description="Wait for actions to load",
                command=self.agent.wait(1.0),
            ),
            TaskStep(
                name="screenshot_actions",
                description="Capture actions section",
                command=self.agent.screenshot(),
            ),
            # Add workflow action
            TaskStep(
                name="find_add_action",
                description="Find add action button",
                command=self.agent.find_elements("add action button or add workflow"),
            ),
            TaskStep(
                name="wait_action_modal",
                description="Wait for action modal",
                command=self.agent.wait(1.0),
            ),
            TaskStep(
                name="select_workflow_type",
                description="Select workflow action type",
                command=self.agent.find_elements("workflow action type or trigger workflow"),
            ),
            TaskStep(
                name="wait_workflow_select",
                description="Wait for workflow selection",
                command=self.agent.wait(0.5),
            ),
            # Search for workflow
            TaskStep(
                name="find_workflow_search",
                description="Find workflow search or dropdown",
                command=self.agent.find_elements("workflow dropdown or search workflows"),
            ),
            TaskStep(
                name="search_workflow",
                description=f"Search for workflow: {workflow_name}",
                command=self.agent.type_text(workflow_name),
                wait_after=1.0,
            ),
            TaskStep(
                name="select_workflow",
                description=f"Select workflow: {workflow_name}",
                command=self.agent.find_elements(f"workflow option {workflow_name}"),
            ),
            # Save
            TaskStep(
                name="find_save",
                description="Find save button",
                command=self.agent.find_elements("save button or confirm"),
            ),
            TaskStep(
                name="wait_save",
                description="Wait for save",
                command=self.agent.wait(1.5),
            ),
            TaskStep(
                name="screenshot_complete",
                description="Capture completed configuration",
                command=self.agent.screenshot(),
            ),
        ]

    # =========================================================================
    # AI Settings Tasks
    # =========================================================================

    def navigate_to_conversation_ai(self) -> list[TaskStep]:
        """Generate steps to navigate to Conversation AI settings."""
        return [
            TaskStep(
                name="navigate_conv_ai",
                description="Navigate to Conversation AI settings",
                command=self.agent.navigate(f"{self.GHL_BASE_URL}/settings/conversation-ai"),
                wait_after=2.0,
            ),
            TaskStep(
                name="screenshot_conv_ai",
                description="Capture Conversation AI page",
                command=self.agent.screenshot(),
            ),
        ]

    def navigate_to_voice_ai(self) -> list[TaskStep]:
        """Generate steps to navigate to Voice AI settings."""
        return [
            TaskStep(
                name="navigate_voice_ai",
                description="Navigate to Voice AI settings",
                command=self.agent.navigate(f"{self.GHL_BASE_URL}/settings/voice-ai"),
                wait_after=2.0,
            ),
            TaskStep(
                name="screenshot_voice_ai",
                description="Capture Voice AI page",
                command=self.agent.screenshot(),
            ),
        ]

    def capture_ai_agent_details(self, agent_name: str) -> list[TaskStep]:
        """Generate steps to capture AI agent configuration details.

        Args:
            agent_name: Name of the agent to capture

        Returns:
            List of TaskSteps to capture agent details
        """
        return [
            TaskStep(
                name="find_agent",
                description=f"Find agent: {agent_name}",
                command=self.agent.find_elements(f"agent {agent_name}"),
            ),
            TaskStep(
                name="wait_details",
                description="Wait for details to load",
                command=self.agent.wait(1.5),
            ),
            TaskStep(
                name="screenshot_details",
                description="Capture agent details",
                command=self.agent.screenshot(),
            ),
            TaskStep(
                name="read_page",
                description="Read page content",
                command=self.agent.read_page(filter_type="all"),
            ),
        ]
