"""Chat service — Claude API integration with GHL tool definitions."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

from ..config import settings


# Tool definitions for Claude API (maps to GHL operations)
TOOLS: list[dict[str, Any]] = [
    {
        "name": "list_contacts",
        "description": "List or search contacts in the current GHL location.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (name, email, phone)"},
                "limit": {"type": "integer", "description": "Max results (default 20)", "default": 20},
            },
        },
    },
    {
        "name": "get_contact",
        "description": "Get full details for a specific contact by ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "contact_id": {"type": "string", "description": "The contact ID"},
            },
            "required": ["contact_id"],
        },
    },
    {
        "name": "create_contact",
        "description": "Create a new contact in the GHL location.",
        "input_schema": {
            "type": "object",
            "properties": {
                "first_name": {"type": "string"},
                "last_name": {"type": "string"},
                "email": {"type": "string"},
                "phone": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["first_name"],
        },
    },
    {
        "name": "add_tag",
        "description": "Add a tag to a contact.",
        "input_schema": {
            "type": "object",
            "properties": {
                "contact_id": {"type": "string"},
                "tag": {"type": "string"},
            },
            "required": ["contact_id", "tag"],
        },
    },
    {
        "name": "list_pipelines",
        "description": "List all pipelines and their stages in the GHL location.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_opportunities",
        "description": "List opportunities, optionally filtered by pipeline.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline_id": {"type": "string", "description": "Filter by pipeline"},
                "limit": {"type": "integer", "default": 20},
            },
        },
    },
    {
        "name": "create_opportunity",
        "description": "Create a new opportunity in a pipeline.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline_id": {"type": "string"},
                "stage_id": {"type": "string"},
                "contact_id": {"type": "string"},
                "name": {"type": "string"},
                "monetary_value": {"type": "number"},
            },
            "required": ["pipeline_id", "stage_id", "name"],
        },
    },
    {
        "name": "send_sms",
        "description": "Send an SMS message to a contact.",
        "input_schema": {
            "type": "object",
            "properties": {
                "contact_id": {"type": "string"},
                "message": {"type": "string"},
            },
            "required": ["contact_id", "message"],
        },
    },
    {
        "name": "send_email",
        "description": "Send an email to a contact.",
        "input_schema": {
            "type": "object",
            "properties": {
                "contact_id": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["contact_id", "subject", "body"],
        },
    },
    {
        "name": "list_workflows",
        "description": "List all workflows defined in the workflow builder.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "run_workflow",
        "description": "Manually trigger a workflow by ID with optional trigger data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "workflow_id": {"type": "string"},
                "trigger_data": {"type": "object", "description": "Data to pass to workflow context"},
            },
            "required": ["workflow_id"],
        },
    },
]


async def execute_tool(name: str, args: dict) -> dict[str, Any]:
    """Execute a tool call by dispatching to the appropriate GHL API."""
    try:
        if name == "list_contacts":
            return await _list_contacts(args)
        elif name == "get_contact":
            return await _get_contact(args)
        elif name == "create_contact":
            return await _create_contact(args)
        elif name == "add_tag":
            return await _add_tag(args)
        elif name == "list_pipelines":
            return await _list_pipelines()
        elif name == "list_opportunities":
            return await _list_opportunities(args)
        elif name == "create_opportunity":
            return await _create_opportunity(args)
        elif name == "send_sms":
            return await _send_sms(args)
        elif name == "send_email":
            return await _send_email(args)
        elif name == "list_workflows":
            return await _list_workflows()
        elif name == "run_workflow":
            return await _run_workflow(args)
        else:
            return {"error": f"Unknown tool: {name}"}
    except Exception as e:
        return {"error": str(e)}


async def stream_chat(
    messages: list[dict],
    system: str | None = None,
) -> AsyncIterator[dict]:
    """Stream a chat response from Claude, handling tool use loops.

    Yields dicts with type: "text", "tool_use", "tool_result", "done", or "error".
    """
    try:
        import anthropic
    except ImportError:
        yield {"type": "error", "content": "anthropic package not installed. Run: pip install anthropic"}
        return

    api_key = settings.anthropic_api_key
    if not api_key:
        yield {"type": "error", "content": "Set WF_ANTHROPIC_API_KEY environment variable."}
        return

    client = anthropic.AsyncAnthropic(api_key=api_key)

    default_system = (
        "You are MaxLevel AI, a helpful assistant for managing GoHighLevel CRM operations. "
        "You can search contacts, manage pipelines, send messages, and run automation workflows. "
        "Be concise and action-oriented. When showing data, format it clearly."
    )

    working_messages = list(messages)

    # Tool use loop — keep calling Claude until no more tool_use blocks
    max_tool_rounds = 10
    rounds = 0
    while True:
        rounds += 1
        if rounds > max_tool_rounds:
            yield {"type": "error", "content": "Too many tool rounds. Please try a simpler request."}
            return
        text_buffer = ""

        async with client.messages.stream(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2048,
            system=system or default_system,
            messages=working_messages,
            tools=TOOLS,
        ) as stream:
            tool_uses = []
            async for event in stream:
                if event.type == "content_block_start":
                    if event.content_block.type == "tool_use":
                        tool_uses.append({
                            "id": event.content_block.id,
                            "name": event.content_block.name,
                            "input_json": "",
                        })
                elif event.type == "content_block_delta":
                    if hasattr(event.delta, "text"):
                        text_buffer += event.delta.text
                        yield {"type": "text", "content": event.delta.text}
                    elif hasattr(event.delta, "partial_json"):
                        if tool_uses:
                            tool_uses[-1]["input_json"] += event.delta.partial_json

            response = await stream.get_final_message()

        # If no tool use, we're done
        if response.stop_reason != "tool_use":
            yield {"type": "done"}
            return

        # Process tool calls
        # Add assistant message with all content blocks
        working_messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                yield {
                    "type": "tool_use",
                    "name": block.name,
                    "input": block.input,
                }

                result = await execute_tool(block.name, block.input)

                yield {
                    "type": "tool_result",
                    "name": block.name,
                    "result": result,
                }

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                })

        # Add tool results and loop back
        working_messages.append({"role": "user", "content": tool_results})


# --- GHL API handlers ---

async def _get_ghl_client():
    from maxlevel.api import GHLClient
    return GHLClient.from_session()


async def _list_contacts(args: dict) -> dict:
    async with await _get_ghl_client() as ghl:
        return await ghl.contacts.list(
            query=args.get("query"),
            limit=args.get("limit", 20),
        )


async def _get_contact(args: dict) -> dict:
    async with await _get_ghl_client() as ghl:
        return await ghl.contacts.get(args["contact_id"])


async def _create_contact(args: dict) -> dict:
    async with await _get_ghl_client() as ghl:
        return await ghl.contacts.create(**args)


async def _add_tag(args: dict) -> dict:
    async with await _get_ghl_client() as ghl:
        return await ghl.contacts.add_tag(args["contact_id"], args["tag"])


async def _list_pipelines() -> dict:
    async with await _get_ghl_client() as ghl:
        return await ghl.opportunities.list_pipelines()


async def _list_opportunities(args: dict) -> dict:
    async with await _get_ghl_client() as ghl:
        return await ghl.opportunities.list(
            pipeline_id=args.get("pipeline_id"),
            limit=args.get("limit", 20),
        )


async def _create_opportunity(args: dict) -> dict:
    async with await _get_ghl_client() as ghl:
        return await ghl.opportunities.create(**args)


async def _send_sms(args: dict) -> dict:
    async with await _get_ghl_client() as ghl:
        return await ghl.conversations.send_sms(args["contact_id"], args["message"])


async def _send_email(args: dict) -> dict:
    async with await _get_ghl_client() as ghl:
        return await ghl.conversations.send_email(
            args["contact_id"], args["subject"], args["body"]
        )


async def _list_workflows() -> dict:
    from ..database import async_session_factory
    from ..services import workflow_svc

    async with async_session_factory() as db:
        workflows = await workflow_svc.list_workflows(db)
        return {
            "workflows": [
                {"id": str(w.id), "name": w.name, "status": w.status}
                for w in workflows
            ]
        }


async def _run_workflow(args: dict) -> dict:
    import uuid
    from ..database import async_session_factory
    from ..engine.runner import WorkflowRunner

    wf_id = uuid.UUID(args["workflow_id"])
    trigger_data = args.get("trigger_data", {})

    async with async_session_factory() as db:
        runner = WorkflowRunner(db)
        execution = await runner.run(wf_id, trigger_data=trigger_data)
        return {
            "execution_id": str(execution.id),
            "status": execution.status,
            "steps_completed": execution.steps_completed,
        }
