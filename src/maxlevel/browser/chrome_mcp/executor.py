"""Task executor for Chrome MCP browser automation.

This module provides execution plan generation and formatting for browser
automation tasks. The actual MCP tool execution is performed by Claude Code.

Since Claude Code runs the MCP tools directly, this module generates
human-readable plans that describe the steps to be executed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .tasks import TaskStep
from .ai_tasks import AIBrowserTasks


@dataclass
class ExecutionPlan:
    """Plan for browser automation execution.

    Contains a sequence of TaskSteps with metadata for display and execution.
    """

    steps: list[TaskStep]
    description: str
    trigger_type: str | None = None
    target_name: str | None = None

    def to_mcp_commands(self) -> list[dict[str, Any]]:
        """Convert steps to MCP command dicts for reference."""
        return [step.command for step in self.steps]

    def print_plan(self, console: Console) -> None:
        """Print human-readable plan to console."""
        console.print(f"\n[bold cyan]{self.description}[/bold cyan]\n")

        table = Table(show_header=True, header_style="bold")
        table.add_column("#", style="dim", width=4)
        table.add_column("Step", style="cyan")
        table.add_column("Description", style="white")

        for i, step in enumerate(self.steps, 1):
            table.add_row(str(i), step.name, step.description)

        console.print(table)
        console.print()

    def print_summary(self, console: Console) -> None:
        """Print a brief summary of the plan."""
        console.print(
            Panel(
                f"[bold]{self.description}[/bold]\n\n"
                f"Steps: {len(self.steps)}\n"
                + (f"Trigger: {self.trigger_type}\n" if self.trigger_type else "")
                + (f"Target: {self.target_name}" if self.target_name else ""),
                title="Execution Plan",
            )
        )


def create_workflow_plan(
    tab_id: int,
    name: str,
    trigger: str = "manual",
) -> ExecutionPlan:
    """Create execution plan for workflow creation.

    Args:
        tab_id: Chrome MCP tab ID
        name: Workflow name to create
        trigger: Trigger type ("conversation_ai", "voice_ai", "manual")

    Returns:
        ExecutionPlan with steps to create the workflow
    """
    tasks = AIBrowserTasks(tab_id=tab_id)
    steps = tasks.create_workflow_for_ai(name=name, trigger=trigger)

    trigger_display = {
        "conversation_ai": "Conversation AI",
        "voice_ai": "Voice AI",
        "manual": "Manual/Contact Added",
    }.get(trigger, trigger)

    return ExecutionPlan(
        steps=steps,
        description=f"Create workflow '{name}' with {trigger_display} trigger",
        trigger_type=trigger,
        target_name=name,
    )


def connect_workflow_plan(
    tab_id: int,
    workflow_name: str,
    agent_name: str,
    agent_type: str = "conversation",
) -> ExecutionPlan:
    """Create execution plan for connecting workflow to agent.

    Args:
        tab_id: Chrome MCP tab ID
        workflow_name: Name of workflow to connect
        agent_name: Name of AI agent to connect to
        agent_type: "conversation" or "voice"

    Returns:
        ExecutionPlan with steps to connect workflow to agent
    """
    tasks = AIBrowserTasks(tab_id=tab_id)
    steps = tasks.connect_workflow_to_agent(
        workflow_name=workflow_name,
        agent_name=agent_name,
        agent_type=agent_type,
    )

    type_display = "Conversation AI" if agent_type == "conversation" else "Voice AI"

    return ExecutionPlan(
        steps=steps,
        description=f"Connect workflow '{workflow_name}' to {type_display} agent '{agent_name}'",
        trigger_type=agent_type,
        target_name=workflow_name,
    )


def navigate_to_ai_settings_plan(
    tab_id: int,
    ai_type: str = "conversation",
) -> ExecutionPlan:
    """Create execution plan for navigating to AI settings.

    Args:
        tab_id: Chrome MCP tab ID
        ai_type: "conversation" or "voice"

    Returns:
        ExecutionPlan with navigation steps
    """
    tasks = AIBrowserTasks(tab_id=tab_id)

    if ai_type == "conversation":
        steps = tasks.navigate_to_conversation_ai()
        description = "Navigate to Conversation AI settings"
    else:
        steps = tasks.navigate_to_voice_ai()
        description = "Navigate to Voice AI settings"

    return ExecutionPlan(
        steps=steps,
        description=description,
        trigger_type=ai_type,
    )


def capture_agent_details_plan(
    tab_id: int,
    agent_name: str,
) -> ExecutionPlan:
    """Create execution plan for capturing AI agent details.

    Args:
        tab_id: Chrome MCP tab ID
        agent_name: Name of agent to capture

    Returns:
        ExecutionPlan with steps to capture agent configuration
    """
    tasks = AIBrowserTasks(tab_id=tab_id)
    steps = tasks.capture_ai_agent_details(agent_name)

    return ExecutionPlan(
        steps=steps,
        description=f"Capture details for agent '{agent_name}'",
        target_name=agent_name,
    )
