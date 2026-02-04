"""Voice AI API - Full CRUD operations for GHL voice AI agents."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .client import GHLClient


class VoiceAIAPI:
    """Voice AI API for GoHighLevel.

    Manage AI voice agents that can handle phone calls, schedule appointments,
    and interact with customers via voice.

    Usage:
        async with GHLClient.from_session() as ghl:
            # List available voices
            voices = await ghl.voice_ai.list_voices()

            # List agents
            agents = await ghl.voice_ai.list_agents()

            # Create agent
            agent = await ghl.voice_ai.create_agent(
                name="Appointment Bot",
                voice_id="voice_id",
                prompt="You schedule appointments for our dental office...",
            )

            # View call logs
            calls = await ghl.voice_ai.list_calls(agent_id="agent_id")

            # Get call transcript
            transcript = await ghl.voice_ai.get_call("call_id")
    """

    def __init__(self, client: "GHLClient"):
        self._client = client

    @property
    def _location_id(self) -> str:
        """Get location ID or raise error."""
        lid = self._client.config.location_id
        if not lid:
            raise ValueError("location_id required. Set via config or run 'ghl auth login'")
        return lid

    # =========================================================================
    # Voices
    # =========================================================================

    async def list_voices(self, location_id: str | None = None) -> dict[str, Any]:
        """List available voice profiles.

        Returns all voice options that can be used for voice AI agents,
        including built-in voices and any custom cloned voices.

        Args:
            location_id: Override default location

        Returns:
            {"voices": [{"id": ..., "name": ..., "preview_url": ...}, ...]}
        """
        lid = location_id or self._location_id
        return await self._client._get("/voice-ai/voices", locationId=lid)

    # =========================================================================
    # Agents
    # =========================================================================

    async def list_agents(
        self,
        location_id: str | None = None,
        limit: int = 50,
        skip: int = 0,
    ) -> dict[str, Any]:
        """List all voice AI agents.

        Args:
            location_id: Override default location
            limit: Max agents to return
            skip: Number of agents to skip (for pagination)

        Returns:
            {"agents": [...], "total": N}
        """
        lid = location_id or self._location_id
        return await self._client._get(
            "/voice-ai/agents",
            locationId=lid,
            limit=limit,
            skip=skip,
        )

    async def get_agent(self, agent_id: str) -> dict[str, Any]:
        """Get a single voice AI agent by ID.

        Args:
            agent_id: The agent ID

        Returns:
            {"agent": {...}} with agent configuration
        """
        return await self._client._get(f"/voice-ai/agents/{agent_id}")

    async def create_agent(
        self,
        name: str,
        voice_id: str,
        prompt: str | None = None,
        phone_number_id: str | None = None,
        greeting: str | None = None,
        model: str = "gpt-4",
        temperature: float = 0.7,
        location_id: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Create a new voice AI agent.

        Args:
            name: Agent name
            voice_id: ID of the voice profile to use
            prompt: System prompt for the AI
            phone_number_id: Phone number ID to assign to this agent
            greeting: Initial greeting when answering calls
            model: AI model to use (default: gpt-4)
            temperature: Response creativity (0-1, default: 0.7)
            location_id: Override default location
            **kwargs: Additional agent configuration

        Returns:
            {"agent": {...}} with created agent data
        """
        lid = location_id or self._location_id

        data = {
            "locationId": lid,
            "name": name,
            "voiceId": voice_id,
            "model": model,
            "temperature": temperature,
        }

        if prompt:
            data["prompt"] = prompt
        if phone_number_id:
            data["phoneNumberId"] = phone_number_id
        if greeting:
            data["greeting"] = greeting

        data.update(kwargs)

        return await self._client._post("/voice-ai/agents", data)

    async def update_agent(
        self,
        agent_id: str,
        name: str | None = None,
        voice_id: str | None = None,
        prompt: str | None = None,
        phone_number_id: str | None = None,
        greeting: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        enabled: bool | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Update an existing voice AI agent.

        Note: Voice AI uses PATCH for updates.

        Args:
            agent_id: The agent ID to update
            name: New agent name
            voice_id: New voice profile ID
            prompt: New system prompt
            phone_number_id: New phone number ID
            greeting: New greeting message
            model: New AI model
            temperature: New temperature setting
            enabled: Enable/disable the agent
            **kwargs: Additional fields to update

        Returns:
            {"agent": {...}} with updated agent data
        """
        data = {}

        if name is not None:
            data["name"] = name
        if voice_id is not None:
            data["voiceId"] = voice_id
        if prompt is not None:
            data["prompt"] = prompt
        if phone_number_id is not None:
            data["phoneNumberId"] = phone_number_id
        if greeting is not None:
            data["greeting"] = greeting
        if model is not None:
            data["model"] = model
        if temperature is not None:
            data["temperature"] = temperature
        if enabled is not None:
            data["enabled"] = enabled

        data.update(kwargs)

        return await self._client._patch(f"/voice-ai/agents/{agent_id}", data)

    async def delete_agent(self, agent_id: str) -> dict[str, Any]:
        """Delete a voice AI agent.

        Args:
            agent_id: The agent ID to delete

        Returns:
            {"succeeded": true} or error
        """
        return await self._client._delete(f"/voice-ai/agents/{agent_id}")

    # =========================================================================
    # Actions
    # =========================================================================

    async def list_actions(self, agent_id: str) -> dict[str, Any]:
        """List actions attached to a voice agent.

        Actions are triggered during calls based on conversation context.

        Args:
            agent_id: The agent ID

        Returns:
            {"actions": [...]}
        """
        return await self._client._get(f"/voice-ai/agents/{agent_id}/actions")

    async def create_action(
        self,
        agent_id: str,
        action_type: str,
        name: str,
        trigger_condition: str | None = None,
        workflow_id: str | None = None,
        webhook_url: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Create an action for a voice agent.

        Args:
            agent_id: The agent ID
            action_type: Type of action ("workflow", "webhook", "transfer", "hangup")
            name: Action name
            trigger_condition: When to trigger (e.g., "intent:schedule_appointment")
            workflow_id: Workflow ID if type is "workflow"
            webhook_url: Webhook URL if type is "webhook"
            **kwargs: Additional action configuration

        Returns:
            {"action": {...}} with created action data
        """
        data = {
            "type": action_type,
            "name": name,
        }

        if trigger_condition:
            data["triggerCondition"] = trigger_condition
        if workflow_id:
            data["workflowId"] = workflow_id
        if webhook_url:
            data["webhookUrl"] = webhook_url

        data.update(kwargs)

        return await self._client._post(f"/voice-ai/agents/{agent_id}/actions", data)

    async def delete_action(self, agent_id: str, action_id: str) -> dict[str, Any]:
        """Delete an action from a voice agent.

        Args:
            agent_id: The agent ID
            action_id: The action ID to delete

        Returns:
            {"succeeded": true} or error
        """
        return await self._client._delete(
            f"/voice-ai/agents/{agent_id}/actions/{action_id}"
        )

    # =========================================================================
    # Call Logs
    # =========================================================================

    async def list_calls(
        self,
        agent_id: str | None = None,
        contact_id: str | None = None,
        status: str | None = None,
        location_id: str | None = None,
        limit: int = 50,
        skip: int = 0,
    ) -> dict[str, Any]:
        """List voice AI call logs.

        Args:
            agent_id: Filter by agent ID
            contact_id: Filter by contact ID
            status: Filter by status ("completed", "failed", "in_progress")
            location_id: Override default location
            limit: Max calls to return
            skip: Number to skip (for pagination)

        Returns:
            {"calls": [...], "total": N}
        """
        lid = location_id or self._location_id
        params = {"locationId": lid, "limit": limit, "skip": skip}

        if agent_id:
            params["agentId"] = agent_id
        if contact_id:
            params["contactId"] = contact_id
        if status:
            params["status"] = status

        return await self._client._get("/voice-ai/calls", **params)

    async def get_call(self, call_id: str) -> dict[str, Any]:
        """Get a single call by ID, including transcript.

        Args:
            call_id: The call ID

        Returns:
            {"call": {...}} with full call data including:
            - transcript: Full conversation transcript
            - duration: Call duration
            - status: Call status
            - recordingUrl: Recording URL if available
            - summary: AI-generated call summary
        """
        return await self._client._get(f"/voice-ai/calls/{call_id}")

    # =========================================================================
    # Phone Numbers
    # =========================================================================

    async def list_phone_numbers(
        self,
        location_id: str | None = None,
    ) -> dict[str, Any]:
        """List phone numbers available for voice AI.

        Args:
            location_id: Override default location

        Returns:
            {"phoneNumbers": [...]}
        """
        lid = location_id or self._location_id
        return await self._client._get("/voice-ai/phone-numbers", locationId=lid)

    async def assign_phone_number(
        self,
        agent_id: str,
        phone_number_id: str,
    ) -> dict[str, Any]:
        """Assign a phone number to a voice agent.

        Args:
            agent_id: The agent ID
            phone_number_id: The phone number ID to assign

        Returns:
            {"agent": {...}} with updated agent data
        """
        return await self._client._patch(
            f"/voice-ai/agents/{agent_id}",
            {"phoneNumberId": phone_number_id},
        )

    # =========================================================================
    # Settings
    # =========================================================================

    async def get_settings(self, location_id: str | None = None) -> dict[str, Any]:
        """Get voice AI settings for location.

        Args:
            location_id: Override default location

        Returns:
            {"settings": {...}} with voice AI configuration
        """
        lid = location_id or self._location_id
        return await self._client._get("/voice-ai/settings", locationId=lid)

    async def update_settings(
        self,
        location_id: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Update voice AI settings.

        Args:
            location_id: Override default location
            **kwargs: Settings to update

        Returns:
            {"settings": {...}} with updated settings
        """
        lid = location_id or self._location_id
        data = {"locationId": lid}
        data.update(kwargs)
        return await self._client._patch("/voice-ai/settings", data)
