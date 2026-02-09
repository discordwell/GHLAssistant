"""Workflow export/rebuild via browser automation (loss-minimizing).

GHL workflow creation is generally not available via API, so we rely on UI
automation to recreate workflows when needed.

Current scope (intentionally minimal):
- Recreate missing workflows by name (and best-effort trigger selection)
- Preserve raw workflow payloads locally (already done on import)
- After UI creation, reconcile new workflow IDs and archive raw detail payloads

This is designed primarily for "rebuildability" and backup/restore workflows
for a location, not for perfect semantic round-tripping of every workflow step.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from maxlevel.browser.chrome_mcp.tasks import GHLBrowserTasks, TaskStep

from ..models.ghl_raw import GHLRawEntity
from ..models.form import Form
from ..models.location import Location
from ..models.pipeline import Pipeline, PipelineStage
from ..schemas.sync import SyncResult
from ..models.tag import Tag
from .archive import write_sync_archive
from .browser_fallback import execute_browser_export_plan
from .raw_store import upsert_raw_entity


def _serialize_step(step: TaskStep) -> dict[str, Any]:
    return {
        "name": step.name,
        "description": step.description,
        "command": step.command,
        "wait_after": step.wait_after,
        "screenshot_after": step.screenshot_after,
        "required": step.required,
    }


def _normalize_name(value: str | None) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().lower().split())


def _extract_items(resp: dict[str, Any], key: str) -> list[dict[str, Any]]:
    raw = resp.get(key, [])
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        nested = raw.get(key)
        if isinstance(nested, list):
            return [item for item in nested if isinstance(item, dict)]
    return []


def _extract_id(payload: dict[str, Any]) -> str:
    for key in ("id", "_id"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _workflow_payload(raw_payload: dict[str, Any]) -> dict[str, Any]:
    """Return the best candidate object representing the workflow itself."""
    if not isinstance(raw_payload, dict):
        return {}
    wf = raw_payload.get("workflow")
    if isinstance(wf, dict) and wf:
        return wf
    return raw_payload


def _workflow_name(raw_payload: dict[str, Any]) -> str:
    wf = _workflow_payload(raw_payload)
    name = wf.get("name") or wf.get("title")
    return str(name).strip() if isinstance(name, str) and name.strip() else ""


def _workflow_status(raw_payload: dict[str, Any]) -> str:
    wf = _workflow_payload(raw_payload)
    status = wf.get("status")
    if isinstance(status, str) and status.strip():
        return status.strip().lower()
    return "draft"


def _workflow_trigger(raw_payload: dict[str, Any]) -> str:
    """Best-effort trigger type string for UI selection."""
    wf = _workflow_payload(raw_payload)
    for key in ("triggerType", "trigger_type", "trigger", "eventType", "event_type"):
        value = wf.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()

    trigger = wf.get("trigger")
    if isinstance(trigger, dict):
        t = trigger.get("type") or trigger.get("triggerType")
        if isinstance(t, str) and t.strip():
            return t.strip().lower()

    return "manual"


def _map_trigger_for_ui(trigger: str) -> str:
    """Map raw/API trigger labels to our UI trigger keywords."""
    t = (trigger or "").strip().lower()
    if not t:
        return "manual"

    aliases = {
        "manual": "manual",
        "contact_added": "manual",
        "contactadded": "manual",
        "contact_created": "contact_created",
        "contactcreate": "contact_created",
        "tag_added": "tag_added",
        "contacttagupdate": "tag_added",
        "tag_removed": "tag_removed",
        "opportunity_stage_changed": "opportunity_stage_changed",
        "opportunitystageupdate": "opportunity_stage_changed",
        "form_submitted": "form_submitted",
        "formsubmission": "form_submitted",
        "conversation_ai": "conversation_ai",
        "voice_ai": "voice_ai",
    }
    return aliases.get(t, t)


def _workflow_trigger_config_raw(raw_payload: dict[str, Any]) -> dict[str, Any]:
    """Extract best-effort trigger config fields from a workflow payload.

    GHL workflow triggers vary by account and by API version; treat these as hints.
    """
    wf = _workflow_payload(raw_payload)
    trigger_obj = _to_dict(wf.get("trigger"))
    candidates = [
        trigger_obj,
        _to_dict(trigger_obj.get("filters")),
        _to_dict(trigger_obj.get("config")),
        wf,
    ]

    def _first_from(keys: list[str]) -> str | None:
        for c in candidates:
            value = _first_str(c, keys)
            if value:
                return value
        return None

    config: dict[str, Any] = {}

    # Tags
    tag_id = _first_from(["tagId", "tag_id"])
    tag_name = _first_from(["tagName", "tag", "tag_name"])
    if tag_id:
        config["tag_id"] = tag_id
    if tag_name:
        config["tag"] = tag_name

    # Forms
    form_id = _first_from(["formId", "form_id"])
    form_name = _first_from(["formName", "form", "form_name"])
    if form_id:
        config["form_id"] = form_id
    if form_name:
        config["form"] = form_name

    # Opportunities
    pipeline_id = _first_from(["pipelineId", "pipeline_id"])
    stage_id = _first_from(["pipelineStageId", "pipeline_stage_id", "stageId", "stage_id"])
    pipeline_name = _first_from(["pipelineName", "pipeline"])
    stage_name = _first_from(["stageName", "stage"])
    if pipeline_id:
        config["pipeline_id"] = pipeline_id
    if stage_id:
        config["stage_id"] = stage_id
    if pipeline_name:
        config["pipeline"] = pipeline_name
    if stage_name:
        config["stage"] = stage_name

    return config


async def _resolve_trigger_config_for_ui(
    db: AsyncSession,
    location: Location,
    *,
    trigger: str,
    raw_config: dict[str, Any],
) -> dict[str, str]:
    """Resolve trigger config into UI-friendly names using local lookup tables."""
    trigger = (trigger or "").strip().lower()
    raw_config = raw_config if isinstance(raw_config, dict) else {}
    resolved: dict[str, str] = {}

    if trigger in {"tag_added", "tag_removed"}:
        tag = raw_config.get("tag")
        if isinstance(tag, str) and tag.strip():
            resolved["tag"] = tag.strip()
        else:
            tag_id = raw_config.get("tag_id")
            if isinstance(tag_id, str) and tag_id.strip():
                row = (
                    await db.execute(
                        select(Tag).where(
                            Tag.location_id == location.id,
                            Tag.ghl_id == tag_id.strip(),
                        )
                    )
                ).scalars().first()
                if row and isinstance(row.name, str) and row.name.strip():
                    resolved["tag"] = row.name.strip()

    if trigger == "form_submitted":
        form = raw_config.get("form")
        if isinstance(form, str) and form.strip():
            resolved["form"] = form.strip()
        else:
            form_id = raw_config.get("form_id")
            if isinstance(form_id, str) and form_id.strip():
                row = (
                    await db.execute(
                        select(Form).where(
                            Form.location_id == location.id,
                            Form.ghl_id == form_id.strip(),
                        )
                    )
                ).scalars().first()
                if row and isinstance(row.name, str) and row.name.strip():
                    resolved["form"] = row.name.strip()

    if trigger == "opportunity_stage_changed":
        pipeline = raw_config.get("pipeline")
        if isinstance(pipeline, str) and pipeline.strip():
            resolved["pipeline"] = pipeline.strip()
        else:
            pipeline_id = raw_config.get("pipeline_id")
            if isinstance(pipeline_id, str) and pipeline_id.strip():
                row = (
                    await db.execute(
                        select(Pipeline).where(
                            Pipeline.location_id == location.id,
                            Pipeline.ghl_id == pipeline_id.strip(),
                        )
                    )
                ).scalars().first()
                if row and isinstance(row.name, str) and row.name.strip():
                    resolved["pipeline"] = row.name.strip()

        stage = raw_config.get("stage")
        if isinstance(stage, str) and stage.strip():
            resolved["stage"] = stage.strip()
        else:
            stage_id = raw_config.get("stage_id")
            if isinstance(stage_id, str) and stage_id.strip():
                row = (
                    await db.execute(
                        select(PipelineStage)
                        .join(Pipeline, Pipeline.id == PipelineStage.pipeline_id)
                        .where(
                            Pipeline.location_id == location.id,
                            PipelineStage.ghl_id == stage_id.strip(),
                        )
                    )
                ).scalars().first()
                if row and isinstance(row.name, str) and row.name.strip():
                    resolved["stage"] = row.name.strip()

    return resolved


@dataclass(frozen=True)
class ParsedWorkflowStep:
    """Best-effort parsed workflow step we can attempt to recreate via UI."""

    kind: str
    config: dict[str, Any]
    label: str = ""
    confidence: float = 0.5
    source: str | None = None


def _to_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _to_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _get_nested(obj: dict[str, Any], keys: list[str]) -> Any:
    cur: Any = obj
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _first_str(payload: dict[str, Any], keys: list[str]) -> str:
    """Search common locations for a string field (payload then payload.config-like)."""
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    for container_key in ("config", "settings", "data", "params", "meta"):
        container = payload.get(container_key)
        if not isinstance(container, dict):
            continue
        for key in keys:
            value = container.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    return ""


def _first_number(payload: dict[str, Any], keys: list[str]) -> int | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, (int, float)):
            return int(value)
    for container_key in ("config", "settings", "data", "params", "meta"):
        container = payload.get(container_key)
        if not isinstance(container, dict):
            continue
        for key in keys:
            value = container.get(key)
            if isinstance(value, (int, float)):
                return int(value)
    return None


def _collect_step_candidates(raw_payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Collect step-like dicts from common workflow payload shapes."""
    wf = _workflow_payload(raw_payload)

    # Prefer obvious ordered lists when present.
    for container in (wf, raw_payload):
        if not isinstance(container, dict):
            continue
        for key in ("steps", "actions", "nodes", "elements"):
            value = container.get(key)
            if isinstance(value, list) and any(isinstance(item, dict) for item in value):
                return [item for item in value if isinstance(item, dict)]

    # Fallback: traverse workflow payload and gather dicts that look like actions.
    candidates: list[dict[str, Any]] = []
    queue: list[Any] = [wf]
    visited = 0
    while queue and visited < 4000:
        cur = queue.pop(0)
        visited += 1

        if isinstance(cur, dict):
            type_hint = cur.get("type") or cur.get("actionType") or cur.get("eventType")
            has_type_hint = isinstance(type_hint, str) and bool(type_hint.strip())
            has_config = isinstance(cur.get("config"), dict) or isinstance(cur.get("settings"), dict)
            has_payload_fields = any(
                key in cur
                for key in (
                    "message",
                    "body",
                    "subject",
                    "tag",
                    "tagName",
                    "url",
                    "delay",
                    "minutes",
                    "seconds",
                )
            )
            if has_type_hint and (has_config or has_payload_fields):
                candidates.append(cur)

            for value in cur.values():
                if isinstance(value, (dict, list)):
                    queue.append(value)
            continue

        if isinstance(cur, list):
            for item in cur:
                if isinstance(item, (dict, list)):
                    queue.append(item)

    return candidates


def _candidate_order_key(item: dict[str, Any], fallback: int) -> tuple[int, int]:
    for key in ("position", "index", "order", "sequence", "sort", "stepNumber"):
        value = item.get(key)
        if isinstance(value, int):
            return value, fallback
        if isinstance(value, float):
            return int(value), fallback
    return 999999, fallback


def _map_candidate_to_step(candidate: dict[str, Any]) -> ParsedWorkflowStep | None:
    """Map a candidate dict into a ParsedWorkflowStep we can recreate via UI."""
    c = _to_dict(candidate)
    type_hint = (
        _first_str(c, ["actionType", "type", "eventType", "name", "action", "kind"]) or ""
    ).lower()

    # Delay / wait
    if any(token in type_hint for token in ("wait", "delay", "sleep", "pause", "time")):
        seconds = _first_number(c, ["seconds", "delaySeconds", "durationSeconds"])
        minutes = _first_number(c, ["minutes", "delayMinutes", "durationMinutes"])
        hours = _first_number(c, ["hours", "delayHours", "durationHours"])
        days = _first_number(c, ["days", "delayDays", "durationDays"])
        total = 0
        if isinstance(days, int):
            total += max(0, days) * 86400
        if isinstance(hours, int):
            total += max(0, hours) * 3600
        if isinstance(minutes, int):
            total += max(0, minutes) * 60
        if isinstance(seconds, int):
            total += max(0, seconds)
        if total <= 0:
            total = 60  # default 1m best-effort
        return ParsedWorkflowStep(kind="delay", config={"seconds": int(total)}, label="Wait", confidence=0.6)

    # Send SMS
    if "sms" in type_hint or "text message" in type_hint:
        message = _first_str(c, ["message", "body", "content", "text"])
        if not message:
            return None
        return ParsedWorkflowStep(kind="send_sms", config={"message": message}, label="Send SMS", confidence=0.7)

    # Send Email
    if "email" in type_hint:
        subject = _first_str(c, ["subject", "title"])
        body = _first_str(c, ["body", "message", "content", "html"])
        if not subject and not body:
            return None
        return ParsedWorkflowStep(
            kind="send_email",
            config={"subject": subject, "body": body},
            label="Send Email",
            confidence=0.65,
        )

    # Tags
    if "tag" in type_hint:
        tag = _first_str(c, ["tag", "tagName", "name"])
        if not tag:
            return None
        if any(token in type_hint for token in ("remove", "delete", "untag")):
            return ParsedWorkflowStep(kind="remove_tag", config={"tag": tag}, label="Remove Tag", confidence=0.6)
        return ParsedWorkflowStep(kind="add_tag", config={"tag": tag}, label="Add Tag", confidence=0.6)

    # Webhook
    if "webhook" in type_hint or "http" in type_hint:
        url = _first_str(c, ["url", "endpoint", "webhookUrl"])
        method = (_first_str(c, ["method", "httpMethod"]) or "POST").upper()
        if not url:
            return None
        return ParsedWorkflowStep(kind="http_webhook", config={"url": url, "method": method}, label="Webhook", confidence=0.55)

    # Tasks
    if "task" in type_hint:
        title = _first_str(c, ["title", "name", "taskTitle"]) or "New Task"
        description = _first_str(c, ["description", "body", "notes"])
        return ParsedWorkflowStep(kind="create_task", config={"title": title, "description": description}, label="Create Task", confidence=0.5)

    return None


def parse_workflow_steps(
    raw_payload: dict[str, Any],
    *,
    fidelity: int = 1,
    max_steps: int = 50,
) -> list[ParsedWorkflowStep]:
    """Parse a workflow payload into recreatable steps.

    Fidelity levels:
        1: shell only (no steps)
        2: attempt linear action/delay recreation (best-effort)
    """
    if int(fidelity) < 2:
        return []

    candidates = _collect_step_candidates(raw_payload)
    parsed: list[ParsedWorkflowStep] = []
    seen_fingerprints: set[str] = set()

    # Preserve original ordering as a stable fallback while allowing explicit order fields
    # (position/index/order/etc.) to win when present.
    for _, candidate in sorted(enumerate(candidates), key=lambda pair: _candidate_order_key(pair[1], pair[0])):
        if not isinstance(candidate, dict):
            continue
        step = _map_candidate_to_step(candidate)
        if step is None:
            continue

        # Coarse dedupe by (kind + key fields).
        fp_parts = [step.kind]
        if step.kind in {"send_sms", "send_email"}:
            fp_parts.append(str(step.config.get("subject", ""))[:80])
            fp_parts.append(str(step.config.get("message", ""))[:80])
            fp_parts.append(str(step.config.get("body", ""))[:80])
        if "tag" in step.config:
            fp_parts.append(str(step.config.get("tag", ""))[:80])
        if step.kind == "delay":
            fp_parts.append(str(step.config.get("seconds", "")))
        fp = "|".join(fp_parts)
        if fp in seen_fingerprints:
            continue
        seen_fingerprints.add(fp)

        parsed.append(step)
        if len(parsed) >= int(max_steps):
            break

    return parsed


def _step_to_task_steps(tasks: GHLBrowserTasks, step: ParsedWorkflowStep, *, step_index: int) -> list[TaskStep]:
    """Map parsed step to browser TaskSteps."""
    kind = step.kind
    cfg = step.config or {}

    if kind == "send_sms":
        message = str(cfg.get("message", ""))
        return tasks.add_workflow_action_send_sms_via_ui(message, step_index=step_index)
    if kind == "send_email":
        subject = str(cfg.get("subject", ""))
        body = str(cfg.get("body", ""))
        return tasks.add_workflow_action_send_email_via_ui(subject, body, step_index=step_index)
    if kind == "add_tag":
        tag = str(cfg.get("tag", ""))
        return tasks.add_workflow_action_add_tag_via_ui(tag, step_index=step_index)
    if kind == "remove_tag":
        tag = str(cfg.get("tag", ""))
        return tasks.add_workflow_action_remove_tag_via_ui(tag, step_index=step_index)
    if kind == "delay":
        seconds = cfg.get("seconds")
        seconds_i = int(seconds) if isinstance(seconds, (int, float)) else 60
        return tasks.add_workflow_delay_via_ui(seconds_i, step_index=step_index)
    if kind == "http_webhook":
        url = str(cfg.get("url", ""))
        method = str(cfg.get("method", "POST")).upper()
        return tasks.add_workflow_action_webhook_via_ui(url, method=method, step_index=step_index)
    if kind == "create_task":
        title = str(cfg.get("title", "New Task"))
        description = str(cfg.get("description", ""))
        return tasks.add_workflow_action_create_task_via_ui(title, description=description, step_index=step_index)

    return []


async def build_workflow_rebuild_plan(
    db: AsyncSession,
    location: Location,
    ghl: Any,
    *,
    tab_id: int = 0,
    only_missing: bool = True,
    fidelity: int = 2,
) -> dict[str, Any]:
    """Build a browser-export plan to recreate workflows."""
    if not getattr(location, "ghl_location_id", None):
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tab_id": tab_id,
            "summary": {"workflows": 0, "skipped_existing": 0},
            "items": [],
            "errors": ["Missing location.ghl_location_id; cannot compare remote workflows"],
        }

    # Local: raw workflow payloads (loss-minimizing import store).
    stmt = select(GHLRawEntity).where(
        GHLRawEntity.location_id == location.id,
        GHLRawEntity.entity_type == "workflow",
    )
    local_raw = list((await db.execute(stmt)).scalars().all())

    workflows_by_name: dict[str, dict[str, Any]] = {}
    for row in local_raw:
        payload = row.payload_json if isinstance(row.payload_json, dict) else {}
        name = _workflow_name(payload)
        key = _normalize_name(name)
        if not key:
            continue
        # Keep first seen per normalized name (best effort).
        workflows_by_name.setdefault(
            key,
            {
                "raw_id": row.ghl_id,
                "name": name,
                "payload": payload,
            },
        )

    # Remote: workflow names that already exist (avoid duplicates).
    remote_names: set[str] = set()
    try:
        remote_resp = await ghl.workflows.list(location_id=location.ghl_location_id)
        for item in _extract_items(remote_resp if isinstance(remote_resp, dict) else {}, "workflows"):
            remote_names.add(_normalize_name(str(item.get("name", ""))))
    except Exception as exc:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tab_id": tab_id,
            "summary": {"workflows": 0, "skipped_existing": 0},
            "items": [],
            "errors": [f"Remote workflows list failed: {exc}"],
        }

    tasks = GHLBrowserTasks(tab_id=tab_id)
    items: list[dict[str, Any]] = []
    skipped_existing = 0

    for key, meta in workflows_by_name.items():
        name = meta["name"]
        payload = meta["payload"]
        raw_id = meta["raw_id"]

        if only_missing and key in remote_names:
            skipped_existing += 1
            continue

        trigger = _map_trigger_for_ui(_workflow_trigger(payload))
        status = _workflow_status(payload)

        step_list = tasks.create_workflow_via_ui(
            name=name,
            trigger=trigger,
            status=status,
            include_finalize_steps=False,
        )

        trigger_config_raw = _workflow_trigger_config_raw(payload)
        trigger_config_ui: dict[str, str] = {}
        if int(fidelity) >= 3:
            trigger_config_ui = await _resolve_trigger_config_for_ui(
                db,
                location,
                trigger=trigger,
                raw_config=trigger_config_raw,
            )
            step_list.extend(tasks.configure_workflow_trigger_details_via_ui(trigger, trigger_config_ui))

        parsed_steps = parse_workflow_steps(payload, fidelity=int(fidelity))
        for idx, parsed in enumerate(parsed_steps, start=1):
            step_list.extend(_step_to_task_steps(tasks, parsed, step_index=idx))

        # Finalize (save/publish) after attempting to add actions.
        step_list.extend(tasks.finalize_workflow_via_ui(status=status))

        items.append(
            {
                "domain": "workflows",
                "action": "rebuild_workflow",
                "local_id": str(raw_id),
                "name": name,
                "meta": {
                    "trigger": trigger,
                    "trigger_config": trigger_config_ui,
                    "trigger_config_raw": trigger_config_raw,
                    "status": status,
                    "fidelity": int(fidelity),
                    "parsed_steps": [
                        {"kind": s.kind, "label": s.label, "config": s.config, "confidence": s.confidence}
                        for s in parsed_steps
                    ],
                    "source_raw_workflow_id": str(raw_id),
                },
                "steps": [_serialize_step(s) for s in step_list],
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tab_id": tab_id,
        "location": {
            "id": str(location.id),
            "slug": location.slug,
            "name": location.name,
            "ghl_location_id": location.ghl_location_id,
        },
        "summary": {
            "workflows": len(items),
            "skipped_existing": skipped_existing,
        },
        "items": items,
        "errors": [],
    }


async def export_workflows_via_browser(
    db: AsyncSession,
    location: Location,
    ghl: Any,
    *,
    tab_id: int = 0,
    fidelity: int = 2,
    execute: bool = False,
    profile_name: str = "ghl_session",
    headless: bool = False,
    continue_on_error: bool = True,
    max_find_attempts: int = 3,
    retry_wait_seconds: float = 0.75,
    require_login: bool = True,
    preflight_url: str = "https://app.gohighlevel.com/",
    login_email: str | None = None,
    login_password: str | None = None,
    login_timeout_seconds: int = 120,
) -> SyncResult:
    """Rebuild missing workflows in GHL via UI automation."""
    result = SyncResult()

    plan = await build_workflow_rebuild_plan(
        db,
        location,
        ghl,
        tab_id=tab_id,
        only_missing=True,
        fidelity=int(fidelity),
    )
    items = plan.get("items", [])
    if not isinstance(items, list) or not items:
        # Still archive errors if present.
        archive_key = location.ghl_location_id or location.slug
        if plan.get("errors"):
            write_sync_archive(archive_key, "workflows_browser_export_plan", plan)
            for err in plan.get("errors", []):
                if isinstance(err, str):
                    result.errors.append(f"Workflows export plan error: {err}")
        return result

    archive_key = location.ghl_location_id or location.slug
    plan_path = write_sync_archive(archive_key, "workflows_browser_export_plan", plan)
    if plan_path:
        result.errors.append(
            f"INFO: Workflows browser plan generated at {plan_path} ({len(items)} workflows)"
        )
    else:
        result.errors.append(f"INFO: Workflows browser plan generated ({len(items)} workflows)")

    if not execute:
        result.skipped = len(items)
        return result

    execution = await execute_browser_export_plan(
        plan,
        profile_name=profile_name,
        headless=headless,
        continue_on_error=continue_on_error,
        max_find_attempts=max_find_attempts,
        retry_wait_seconds=retry_wait_seconds,
        require_login=require_login,
        preflight_url=preflight_url,
        login_email=login_email,
        login_password=login_password,
        login_timeout_seconds=login_timeout_seconds,
    )

    execution_path = write_sync_archive(archive_key, "workflows_browser_export_execution", execution)
    items_total = int(execution.get("items_total", len(items)))
    items_completed = int(execution.get("items_completed", 0))
    result.created += items_completed
    result.skipped += max(items_total - items_completed, 0)

    if execution_path:
        result.errors.append(f"INFO: Workflows browser execution archived at {execution_path}")
    if execution.get("success"):
        result.errors.append(f"INFO: Workflows browser execution completed ({items_completed}/{items_total})")
    else:
        result.errors.append(f"WARN: Workflows browser execution incomplete ({items_completed}/{items_total})")
        for err in execution.get("errors", []):
            if isinstance(err, str):
                result.errors.append(f"Workflows browser: {err}")

    # Reconcile new IDs by name and archive raw detail payloads for rebuildability.
    try:
        remote_resp = await ghl.workflows.list(location_id=location.ghl_location_id)
        remote_items = _extract_items(remote_resp if isinstance(remote_resp, dict) else {}, "workflows")
    except Exception as exc:
        result.errors.append(f"WARN: Workflows reconcile skipped (list failed): {exc}")
        return result

    remote_by_name: dict[str, dict[str, Any]] = {}
    for item in remote_items:
        key = _normalize_name(str(item.get("name", "")))
        if key and key not in remote_by_name:
            remote_by_name[key] = item

    # Fetch details concurrently for created workflows, then upsert into raw store.
    sem = asyncio.Semaphore(6)
    now = datetime.now(timezone.utc).isoformat()

    async def _one(item: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
        name = str(item.get("name", "")).strip()
        if not name:
            return "", None
        key = _normalize_name(name)
        remote = remote_by_name.get(key)
        if not remote:
            return name, None
        remote_id = _extract_id(remote)
        if not remote_id:
            return name, None
        async with sem:
            try:
                detail = await ghl.workflows.get(remote_id)
            except Exception:
                detail = None
        if isinstance(detail, dict):
            payload = dict(detail)
            meta = payload.get("_maxlevel")
            if not isinstance(meta, dict):
                meta = {}
            meta.update(
                {
                    "rebuilt_at": now,
                    "rebuilt_from_workflow_id": str(item.get("local_id") or ""),
                }
            )
            payload["_maxlevel"] = meta
            return remote_id, payload
        return remote_id, None

    created_items = [i for i in items if isinstance(i, dict)]
    results = await asyncio.gather(*(_one(i) for i in created_items))

    stored = 0
    inserted = 0
    for remote_id, payload in results:
        if not isinstance(remote_id, str) or not remote_id:
            continue
        if not isinstance(payload, dict):
            continue
        created = await upsert_raw_entity(
            db,
            location=location,
            entity_type="workflow",
            ghl_id=remote_id,
            payload=payload,
            source="browser_export",
        )
        stored += 1
        inserted += 1 if created else 0

    await db.commit()

    reconciliation_summary = {
        "stored_count": stored,
        "inserted_count": inserted,
        "workflows_attempted": len(created_items),
    }
    reconciliation_path = write_sync_archive(
        archive_key,
        "workflows_browser_export_reconciliation",
        reconciliation_summary,
    )
    if reconciliation_path:
        result.errors.append(f"INFO: Workflows reconcile archived at {reconciliation_path}")
    if stored:
        result.updated += stored
        result.errors.append(f"INFO: Workflows reconcile stored {stored} raw payload(s)")

    return result
