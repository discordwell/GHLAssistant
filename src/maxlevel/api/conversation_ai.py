"""Conversation AI API - Full CRUD operations for GHL conversation AI agents."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .client import GHLClient


class ConversationAIAPI:
    """Conversation AI API for GoHighLevel.

    Manage AI chatbot agents that can respond to customers via SMS, email,
    and web chat.

    Usage:
        async with GHLClient.from_session() as ghl:
            # List agents
            agents = await ghl.conversation_ai.list_agents()

            # Create agent
            agent = await ghl.conversation_ai.create_agent(
                name="Support Bot",
                prompt="You are a helpful customer support agent...",
                model="gpt-4",
            )

            # Attach workflow action
            await ghl.conversation_ai.attach_action(
                agent_id="agent_id",
                action_id="workflow_id",
                action_type="workflow",
            )

            # View chat history
            history = await ghl.conversation_ai.list_generations(agent_id="agent_id")
    """

    def __init__(self, client: "GHLClient"):
        self._client = client

    @property
    def _location_id(self) -> str:
        """Get location ID or raise error."""
        lid = self._client.config.location_id
        if not lid:
            raise ValueError("location_id required. Set via config or run 'maxlevel auth login'")
        return lid

    # =========================================================================
    # Agents
    # =========================================================================

    async def list_agents(
        self,
        location_id: str | None = None,
        limit: int = 50,
        skip: int = 0,
    ) -> dict[str, Any]:
        """List all conversation AI agents.

        Args:
            location_id: Override default location
            limit: Max agents to return
            skip: Number of agents to skip (for pagination)

        Returns:
            {"agents": [...], "total": N}
        """
        lid = location_id or self._location_id
        return await self._client._get(
            "/conversation-ai/agents",
            locationId=lid,
            limit=limit,
            skip=skip,
        )

    async def get_agent(self, agent_id: str) -> dict[str, Any]:
        """Get a single conversation AI agent by ID.

        Args:
            agent_id: The agent ID

        Returns:
            {"agent": {...}} with agent configuration
        """
        return await self._client._get(f"/conversation-ai/agents/{agent_id}")

    async def create_agent(
        self,
        name: str,
        prompt: str | None = None,
        model: str = "gpt-4",
        temperature: float = 0.7,
        max_tokens: int = 500,
        channels: list[str] | None = None,
        location_id: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Create a new conversation AI agent.

        Args:
            name: Agent name
            prompt: System prompt for the AI
            model: AI model to use (default: gpt-4)
            temperature: Response creativity (0-1, default: 0.7)
            max_tokens: Max response length (default: 500)
            channels: List of channels to enable ["sms", "email", "webchat"]
            location_id: Override default location
            **kwargs: Additional agent configuration

        Returns:
            {"agent": {...}} with created agent data
        """
        lid = location_id or self._location_id

        data = {
            "locationId": lid,
            "name": name,
            "model": model,
            "temperature": temperature,
            "maxTokens": max_tokens,
        }

        if prompt:
            data["prompt"] = prompt
        if channels:
            data["channels"] = channels

        data.update(kwargs)

        return await self._client._post("/conversation-ai/agents", data)

    async def update_agent(
        self,
        agent_id: str,
        name: str | None = None,
        prompt: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        enabled: bool | None = None,
        channels: list[str] | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Update an existing conversation AI agent.

        Args:
            agent_id: The agent ID to update
            name: New agent name
            prompt: New system prompt
            model: New AI model
            temperature: New temperature setting
            max_tokens: New max tokens
            enabled: Enable/disable the agent
            channels: New list of enabled channels
            **kwargs: Additional fields to update

        Returns:
            {"agent": {...}} with updated agent data
        """
        data = {}

        if name is not None:
            data["name"] = name
        if prompt is not None:
            data["prompt"] = prompt
        if model is not None:
            data["model"] = model
        if temperature is not None:
            data["temperature"] = temperature
        if max_tokens is not None:
            data["maxTokens"] = max_tokens
        if enabled is not None:
            data["enabled"] = enabled
        if channels is not None:
            data["channels"] = channels

        data.update(kwargs)

        return await self._client._put(f"/conversation-ai/agents/{agent_id}", data)

    async def delete_agent(self, agent_id: str) -> dict[str, Any]:
        """Delete a conversation AI agent.

        Args:
            agent_id: The agent ID to delete

        Returns:
            {"succeeded": true} or error
        """
        return await self._client._delete(f"/conversation-ai/agents/{agent_id}")

    # =========================================================================
    # Actions (Workflow Connections)
    # =========================================================================

    async def list_actions(self, agent_id: str) -> dict[str, Any]:
        """List actions attached to an agent.

        Actions are workflows or other automations triggered by the AI agent.

        Args:
            agent_id: The agent ID

        Returns:
            {"actions": [...]}
        """
        return await self._client._get(f"/conversation-ai/agents/{agent_id}/actions")

    async def attach_action(
        self,
        agent_id: str,
        action_id: str,
        action_type: str = "workflow",
        trigger_condition: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Attach an action (workflow) to an agent.

        Args:
            agent_id: The agent ID
            action_id: The workflow/action ID to attach
            action_type: Type of action ("workflow", "webhook", etc.)
            trigger_condition: When to trigger (e.g., "intent:book_appointment")
            **kwargs: Additional action configuration

        Returns:
            {"action": {...}} with created action data
        """
        data = {
            "actionId": action_id,
            "type": action_type,
        }

        if trigger_condition:
            data["triggerCondition"] = trigger_condition

        data.update(kwargs)

        return await self._client._post(
            f"/conversation-ai/agents/{agent_id}/actions", data
        )

    async def remove_action(self, agent_id: str, action_id: str) -> dict[str, Any]:
        """Remove an action from an agent.

        Args:
            agent_id: The agent ID
            action_id: The action ID to remove

        Returns:
            {"succeeded": true} or error
        """
        return await self._client._delete(
            f"/conversation-ai/agents/{agent_id}/actions/{action_id}"
        )

    # =========================================================================
    # Generation History
    # =========================================================================

    async def list_generations(
        self,
        agent_id: str | None = None,
        contact_id: str | None = None,
        conversation_id: str | None = None,
        location_id: str | None = None,
        limit: int = 50,
        skip: int = 0,
    ) -> dict[str, Any]:
        """List AI generation history (chat interactions).

        Args:
            agent_id: Filter by agent ID
            contact_id: Filter by contact ID
            conversation_id: Filter by conversation ID
            location_id: Override default location
            limit: Max generations to return
            skip: Number to skip (for pagination)

        Returns:
            {"generations": [...], "total": N}
        """
        lid = location_id or self._location_id
        params = {"locationId": lid, "limit": limit, "skip": skip}

        if agent_id:
            params["agentId"] = agent_id
        if contact_id:
            params["contactId"] = contact_id
        if conversation_id:
            params["conversationId"] = conversation_id

        return await self._client._get("/conversation-ai/generations", **params)

    async def get_generation(self, generation_id: str) -> dict[str, Any]:
        """Get a single generation by ID.

        Args:
            generation_id: The generation ID

        Returns:
            {"generation": {...}} with full generation data including
            input, output, tokens used, etc.
        """
        return await self._client._get(f"/conversation-ai/generations/{generation_id}")

    # =========================================================================
    # Conversations
    # =========================================================================

    async def list_conversations(
        self,
        agent_id: str,
        location_id: str | None = None,
        limit: int = 50,
        skip: int = 0,
    ) -> dict[str, Any]:
        """List conversations handled by an agent.

        Args:
            agent_id: The agent ID
            location_id: Override default location
            limit: Max conversations to return
            skip: Number to skip (for pagination)

        Returns:
            {"conversations": [...], "total": N}
        """
        lid = location_id or self._location_id
        return await self._client._get(
            f"/conversation-ai/agents/{agent_id}/conversations",
            locationId=lid,
            limit=limit,
            skip=skip,
        )

    # =========================================================================
    # Settings
    # =========================================================================

    async def get_settings(self, location_id: str | None = None) -> dict[str, Any]:
        """Get conversation AI settings for location.

        Args:
            location_id: Override default location

        Returns:
            {"settings": {...}} with AI configuration
        """
        lid = location_id or self._location_id
        return await self._client._get(
            "/conversation-ai/settings", locationId=lid
        )

    async def update_settings(
        self,
        location_id: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Update conversation AI settings.

        Args:
            location_id: Override default location
            **kwargs: Settings to update

        Returns:
            {"settings": {...}} with updated settings
        """
        lid = location_id or self._location_id
        data = {"locationId": lid}
        data.update(kwargs)
        return await self._client._put("/conversation-ai/settings", data)
