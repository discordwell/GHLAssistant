"""Action executors — each wraps a GHL API call."""

from __future__ import annotations

from typing import Any

from .context import ExecutionContext


async def execute_action(action_type: str, config: dict, ctx: ExecutionContext) -> dict:
    """Dispatch to the appropriate action handler."""
    handler = ACTION_HANDLERS.get(action_type)
    if not handler:
        return {"error": f"Unknown action type: {action_type}"}
    return await handler(config, ctx)


async def _get_ghl_client():
    """Get an authenticated GHL client."""
    from maxlevel.api import GHLClient
    return GHLClient.from_session()


async def action_send_sms(config: dict, ctx: ExecutionContext) -> dict:
    contact_id = config.get("contact_id") or ctx.get("contact.id")
    message = config.get("message", "")
    if not contact_id:
        return {"error": "No contact_id available"}

    async with await _get_ghl_client() as ghl:
        result = await ghl.conversations.send_sms(contact_id, message)
    return {"sent": True, "type": "sms", "contact_id": contact_id, "result": result}


async def action_send_email(config: dict, ctx: ExecutionContext) -> dict:
    contact_id = config.get("contact_id") or ctx.get("contact.id")
    subject = config.get("subject", "")
    body = config.get("body", "")
    if not contact_id:
        return {"error": "No contact_id available"}

    async with await _get_ghl_client() as ghl:
        result = await ghl.conversations.send_email(contact_id, subject, body)
    return {"sent": True, "type": "email", "contact_id": contact_id, "result": result}


async def action_add_tag(config: dict, ctx: ExecutionContext) -> dict:
    contact_id = config.get("contact_id") or ctx.get("contact.id")
    tag = config.get("tag", "")
    if not contact_id or not tag:
        return {"error": "contact_id and tag required"}

    async with await _get_ghl_client() as ghl:
        result = await ghl.contacts.add_tag(contact_id, tag)
    return {"tagged": True, "contact_id": contact_id, "tag": tag, "result": result}


async def action_remove_tag(config: dict, ctx: ExecutionContext) -> dict:
    contact_id = config.get("contact_id") or ctx.get("contact.id")
    tag = config.get("tag", "")
    if not contact_id or not tag:
        return {"error": "contact_id and tag required"}

    async with await _get_ghl_client() as ghl:
        result = await ghl.contacts.remove_tag(contact_id, tag)
    return {"untagged": True, "contact_id": contact_id, "tag": tag, "result": result}


async def action_move_opportunity(config: dict, ctx: ExecutionContext) -> dict:
    opportunity_id = config.get("opportunity_id") or ctx.get("opportunity.id")
    stage_id = config.get("stage_id", "")
    if not opportunity_id or not stage_id:
        return {"error": "opportunity_id and stage_id required"}

    async with await _get_ghl_client() as ghl:
        result = await ghl.opportunities.move_stage(opportunity_id, stage_id)
    return {"moved": True, "opportunity_id": opportunity_id, "stage_id": stage_id, "result": result}


async def action_create_task(config: dict, ctx: ExecutionContext) -> dict:
    contact_id = config.get("contact_id") or ctx.get("contact.id")
    title = config.get("title", "New Task")
    due_date = config.get("due_date")
    description = config.get("description")
    if not contact_id:
        return {"error": "No contact_id available"}

    async with await _get_ghl_client() as ghl:
        result = await ghl.contacts.add_task(contact_id, title, due_date, description)
    return {"created": True, "type": "task", "contact_id": contact_id, "result": result}


async def action_update_custom_field(config: dict, ctx: ExecutionContext) -> dict:
    contact_id = config.get("contact_id") or ctx.get("contact.id")
    field_key = config.get("field_key", "")
    value = config.get("value", "")
    if not contact_id or not field_key:
        return {"error": "contact_id and field_key required"}

    async with await _get_ghl_client() as ghl:
        result = await ghl.contacts.update(
            contact_id, custom_fields={field_key: value}
        )
    return {"updated": True, "contact_id": contact_id, "field_key": field_key, "result": result}


async def action_http_webhook(config: dict, ctx: ExecutionContext) -> dict:
    import httpx
    url = config.get("url", "")
    method = config.get("method", "POST").upper()
    headers = config.get("headers", {})
    body = config.get("body", {})

    if not url:
        return {"error": "URL required"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        if method == "GET":
            resp = await client.get(url, headers=headers)
        else:
            resp = await client.post(url, json=body, headers=headers)

    return {
        "status_code": resp.status_code,
        "response": resp.text[:1000],
    }


async def action_add_to_workflow(config: dict, ctx: ExecutionContext) -> dict:
    contact_id = config.get("contact_id") or ctx.get("contact.id")
    workflow_id = config.get("workflow_id", "")
    if not contact_id or not workflow_id:
        return {"error": "contact_id and workflow_id required"}

    async with await _get_ghl_client() as ghl:
        result = await ghl.contacts.add_to_workflow(contact_id, workflow_id)
    return {"added": True, "contact_id": contact_id, "workflow_id": workflow_id, "result": result}


async def action_delay(config: dict, ctx: ExecutionContext) -> dict:
    """Handled by runner directly, but included for completeness."""
    import asyncio
    seconds = config.get("seconds", 0)
    if seconds > 0:
        await asyncio.sleep(min(seconds, 300))
    return {"waited_seconds": seconds}


# Action handler registry
ACTION_HANDLERS: dict[str, Any] = {
    "send_sms": action_send_sms,
    "send_email": action_send_email,
    "add_tag": action_add_tag,
    "remove_tag": action_remove_tag,
    "move_opportunity": action_move_opportunity,
    "create_task": action_create_task,
    "update_custom_field": action_update_custom_field,
    "http_webhook": action_http_webhook,
    "add_to_workflow": action_add_to_workflow,
    "delay": action_delay,
}
