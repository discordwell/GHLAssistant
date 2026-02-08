"""Browser-backed export fallback planning, execution, and reconciliation."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from maxlevel.browser.chrome_mcp.tasks import GHLBrowserTasks, TaskStep

from ..models.campaign import Campaign
from ..models.form import Form
from ..models.funnel import Funnel
from ..models.location import Location
from ..models.survey import Survey
from ..schemas.sync import SyncResult
from .archive import write_sync_archive


def _serialize_step(step: TaskStep) -> dict[str, Any]:
    return {
        "name": step.name,
        "description": step.description,
        "command": step.command,
        "wait_after": step.wait_after,
        "screenshot_after": step.screenshot_after,
        "required": step.required,
    }


def _to_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _extract_items(resp: dict[str, Any], key: str) -> list[dict[str, Any]]:
    raw = resp.get(key, [])
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        nested = raw.get(key)
        if isinstance(nested, list):
            return [item for item in nested if isinstance(item, dict)]
    return []


def _extract_payload(detail: dict[str, Any], key: str) -> dict[str, Any]:
    if isinstance(detail.get(key), dict):
        return detail[key]
    return detail


def _extract_ghl_id(payload: dict[str, Any]) -> str:
    for key in ("id", "_id"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _normalize_name(value: str | None) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().lower().split())


def _safe_name(value: str) -> str:
    token = "".join(ch if ch.isalnum() else "_" for ch in value.lower())
    token = "_".join(part for part in token.split("_") if part)
    return token[:80] or "step"


def _extract_form_fields(form_payload: dict[str, Any], list_payload: dict[str, Any]) -> list[dict[str, Any]]:
    for source in (form_payload, list_payload):
        src = _to_dict(source)
        for key in ("fields", "formFields", "elements"):
            value = src.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _extract_survey_questions(
    survey_payload: dict[str, Any], list_payload: dict[str, Any]
) -> list[dict[str, Any]]:
    for source in (survey_payload, list_payload):
        src = _to_dict(source)
        for key in ("questions", "surveyQuestions", "fields"):
            value = src.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _parse_wait(value: Any) -> float:
    if isinstance(value, (int, float)):
        return max(0.0, min(float(value), 30.0))
    return 0.0


def _parse_repeat(value: Any) -> int:
    if isinstance(value, int):
        return max(1, min(value, 20))
    if isinstance(value, float):
        return max(1, min(int(value), 20))
    return 1


def _target_ids(plan: dict[str, Any], domain: str) -> set[str]:
    ids: set[str] = set()
    for item in plan.get("items", []):
        if not isinstance(item, dict):
            continue
        if item.get("domain") != domain:
            continue
        local_id = item.get("local_id")
        if isinstance(local_id, str) and local_id:
            ids.add(local_id)
    return ids


def _build_find_and_focus_js(query: str) -> str:
    query_json = json.dumps(query)
    return f"""
(() => {{
  const query = {query_json}.trim().toLowerCase();
  if (!query) {{
    return {{ found: false, reason: "empty_query" }};
  }}

  const tokens = query.split(/\\s+/).filter(Boolean);
  const candidates = Array.from(
    document.querySelectorAll(
      "button,input,textarea,select,a,[role='button'],[contenteditable='true'],[aria-label],[placeholder],label"
    )
  );

  let best = null;
  let bestScore = 0;

  for (const el of candidates) {{
    const haystack = [
      el.innerText || "",
      el.textContent || "",
      el.getAttribute("aria-label") || "",
      el.getAttribute("placeholder") || "",
      el.getAttribute("name") || "",
      el.id || "",
      el.getAttribute("data-testid") || ""
    ].join(" ").toLowerCase();

    if (!haystack.trim()) {{
      continue;
    }}

    let score = haystack.includes(query) ? 3 : 0;
    for (const token of tokens) {{
      if (haystack.includes(token)) {{
        score += 1;
      }}
    }}

    if (score > bestScore) {{
      best = el;
      bestScore = score;
    }}
  }}

  if (!best || bestScore <= 0) {{
    return {{ found: false, reason: "no_match" }};
  }}

  best.scrollIntoView({{ behavior: "auto", block: "center" }});
  if (typeof best.focus === "function") {{
    best.focus();
  }}
  if (typeof best.click === "function") {{
    try {{
      best.click();
    }} catch (e) {{
      /* best effort */
    }}
  }}

  return {{
    found: true,
    score: bestScore,
    tag: best.tagName || "",
    preview: ((best.innerText || best.value || best.textContent || "").trim()).slice(0, 120)
  }};
}})()
"""


def _build_type_active_js(text: str) -> str:
    text_json = json.dumps(text)
    return f"""
(() => {{
  const value = {text_json};
  const active = document.activeElement;
  if (!active) {{
    return {{ ok: false, reason: "no_active_element" }};
  }}

  if (active.isContentEditable) {{
    active.focus();
    try {{
      document.execCommand("insertText", false, value);
    }} catch (e) {{
      active.textContent = (active.textContent || "") + value;
    }}
    return {{ ok: true, mode: "contenteditable" }};
  }}

  const tag = (active.tagName || "").toLowerCase();
  if (tag === "input" || tag === "textarea") {{
    active.focus();
    active.value = (active.value || "") + value;
    active.dispatchEvent(new Event("input", {{ bubbles: true }}));
    active.dispatchEvent(new Event("change", {{ bubbles: true }}));
    return {{ ok: true, mode: tag }};
  }}

  return {{ ok: false, reason: "active_not_typable", tag }};
}})()
"""


def _build_key_dispatch_js(key: str, repeat: int) -> str:
    key_json = json.dumps(key)
    return f"""
(() => {{
  const key = {key_json};
  const repeat = {repeat};
  const focusables = Array.from(
    document.querySelectorAll(
      "a[href],button,input,textarea,select,[tabindex]:not([tabindex='-1'])"
    )
  ).filter(el => !el.hasAttribute("disabled"));

  let target = document.activeElement || focusables[0] || document.body;
  if (!target) {{
    return {{ ok: false, reason: "no_target" }};
  }}

  for (let i = 0; i < repeat; i++) {{
    target.dispatchEvent(new KeyboardEvent("keydown", {{ key, bubbles: true }}));
    target.dispatchEvent(new KeyboardEvent("keyup", {{ key, bubbles: true }}));

    if (key === "Enter" && typeof target.click === "function") {{
      try {{
        target.click();
      }} catch (e) {{
        /* ignore */
      }}
    }}

    if (key === "Tab" && focusables.length > 0) {{
      const idx = focusables.indexOf(target);
      target = focusables[(idx + 1 + focusables.length) % focusables.length];
      if (target && typeof target.focus === "function") {{
        target.focus();
      }}
    }}
  }}

  return {{ ok: true }};
}})()
"""


def _get_browser_agent_cls():
    from maxlevel.browser.agent import BrowserAgent

    return BrowserAgent


async def _execute_step_command(agent: Any, step_name: str, command: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(command, dict):
        return {"success": False, "error": "Invalid command payload"}

    tool = command.get("tool")
    params = command.get("params", {})
    if not isinstance(params, dict):
        params = {}

    try:
        if tool == "mcp__claude-in-chrome__navigate":
            url = params.get("url")
            if not isinstance(url, str) or not url:
                return {"success": False, "error": "Navigate step missing url"}
            state = await agent.navigate(url)
            return {"success": True, "data": state}

        if tool == "mcp__claude-in-chrome__find":
            query = params.get("query")
            if not isinstance(query, str) or not query.strip():
                return {"success": False, "error": "Find step missing query"}
            found = await agent.evaluate(_build_find_and_focus_js(query))
            if isinstance(found, dict) and found.get("found"):
                return {"success": True, "data": found}
            return {
                "success": False,
                "error": f"Element not found for query '{query}'",
                "data": found,
            }

        if tool == "mcp__claude-in-chrome__javascript_tool":
            code = params.get("text")
            if not isinstance(code, str) or not code.strip():
                return {"success": False, "error": "JS step missing code"}
            js_result = await agent.evaluate(code)
            return {"success": True, "data": js_result}

        if tool == "mcp__claude-in-chrome__computer":
            action = str(params.get("action", "")).lower()

            if action == "wait":
                duration = _parse_wait(params.get("duration", 0))
                if duration > 0:
                    await asyncio.sleep(duration)
                return {"success": True, "data": {"duration": duration}}

            if action == "screenshot":
                path = await agent.screenshot(_safe_name(step_name))
                return {"success": True, "data": {"path": path}}

            if action == "type":
                text = str(params.get("text", ""))
                typed = await agent.evaluate(_build_type_active_js(text))
                ok = isinstance(typed, dict) and bool(typed.get("ok"))
                if not ok:
                    return {"success": False, "error": "Unable to type into active element", "data": typed}
                return {"success": True, "data": typed}

            if action == "key":
                key = str(params.get("text", "Enter"))
                repeat = _parse_repeat(params.get("repeat", 1))
                dispatched = await agent.evaluate(_build_key_dispatch_js(key, repeat))
                ok = isinstance(dispatched, dict) and bool(dispatched.get("ok"))
                if not ok:
                    return {"success": False, "error": f"Unable to dispatch key '{key}'", "data": dispatched}
                return {"success": True, "data": dispatched}

            if action == "left_click":
                clicked = await agent.evaluate(
                    "(() => { const a = document.activeElement; "
                    "if (!a || typeof a.click !== 'function') return {ok:false}; a.click(); return {ok:true}; })()"
                )
                ok = isinstance(clicked, dict) and bool(clicked.get("ok"))
                if not ok:
                    return {"success": False, "error": "Unable to click active element", "data": clicked}
                return {"success": True, "data": clicked}

            return {"success": False, "error": f"Unsupported computer action '{action}'"}

        return {"success": False, "error": f"Unsupported tool '{tool}'"}

    except Exception as exc:
        return {"success": False, "error": str(exc)}


async def build_browser_export_plan(
    db: AsyncSession,
    location: Location,
    tab_id: int = 0,
) -> dict[str, Any]:
    """Build a browser-executable plan for resources lacking API export support."""
    tasks = GHLBrowserTasks(tab_id=tab_id)

    plan_items: list[dict[str, Any]] = []

    forms = list(
        (
            await db.execute(
                select(Form)
                .where(Form.location_id == location.id, Form.ghl_id == None)  # noqa: E711
                .options(selectinload(Form.fields))
                .order_by(Form.created_at.asc())
            )
        ).scalars()
    )
    for form in forms:
        step_list: list[TaskStep] = tasks.create_form_via_ui(
            name=form.name,
            description=form.description,
            is_active=form.is_active,
        )
        for field in sorted(form.fields, key=lambda f: f.position):
            step_list.extend(
                tasks.add_form_field_via_ui(
                    form_name=form.name,
                    label=field.label,
                    field_type=field.field_type,
                    required=field.is_required,
                )
            )

        plan_items.append(
            {
                "domain": "forms",
                "action": "create_form_with_fields",
                "local_id": str(form.id),
                "name": form.name,
                "steps": [_serialize_step(s) for s in step_list],
            }
        )

    surveys = list(
        (
            await db.execute(
                select(Survey)
                .where(Survey.location_id == location.id, Survey.ghl_id == None)  # noqa: E711
                .options(selectinload(Survey.questions))
                .order_by(Survey.created_at.asc())
            )
        ).scalars()
    )
    for survey in surveys:
        step_list = tasks.create_survey_via_ui(
            name=survey.name,
            description=survey.description,
            is_active=survey.is_active,
        )
        for question in sorted(survey.questions, key=lambda q: q.position):
            step_list.extend(
                tasks.add_survey_question_via_ui(
                    survey_name=survey.name,
                    question_text=question.question_text,
                    question_type=question.question_type,
                    required=question.is_required,
                )
            )

        plan_items.append(
            {
                "domain": "surveys",
                "action": "create_survey_with_questions",
                "local_id": str(survey.id),
                "name": survey.name,
                "steps": [_serialize_step(s) for s in step_list],
            }
        )

    campaigns = list(
        (
            await db.execute(
                select(Campaign)
                .where(Campaign.location_id == location.id, Campaign.ghl_id == None)  # noqa: E711
                .options(selectinload(Campaign.steps))
                .order_by(Campaign.created_at.asc())
            )
        ).scalars()
    )
    for campaign in campaigns:
        step_list = tasks.create_campaign_via_ui(
            name=campaign.name,
            description=campaign.description,
            status=campaign.status,
        )
        for step in sorted(campaign.steps, key=lambda s: s.position):
            step_list.extend(
                tasks.add_campaign_step_via_ui(
                    campaign_name=campaign.name,
                    step_type=step.step_type,
                    subject=step.subject,
                    body=step.body,
                    delay_minutes=step.delay_minutes,
                )
            )

        plan_items.append(
            {
                "domain": "campaigns",
                "action": "create_campaign_with_steps",
                "local_id": str(campaign.id),
                "name": campaign.name,
                "steps": [_serialize_step(s) for s in step_list],
            }
        )

    funnels = list(
        (
            await db.execute(
                select(Funnel)
                .where(Funnel.location_id == location.id, Funnel.ghl_id == None)  # noqa: E711
                .options(selectinload(Funnel.pages))
                .order_by(Funnel.created_at.asc())
            )
        ).scalars()
    )
    for funnel in funnels:
        step_list = tasks.create_funnel_via_ui(
            name=funnel.name,
            description=funnel.description,
            is_published=funnel.is_published,
        )
        for page in sorted(funnel.pages, key=lambda p: p.position):
            step_list.extend(
                tasks.add_funnel_page_via_ui(
                    funnel_name=funnel.name,
                    page_name=page.name,
                    url_slug=page.url_slug,
                    is_published=page.is_published,
                )
            )

        plan_items.append(
            {
                "domain": "funnels",
                "action": "create_funnel_with_pages",
                "local_id": str(funnel.id),
                "name": funnel.name,
                "steps": [_serialize_step(s) for s in step_list],
            }
        )

    summary: dict[str, int] = {
        "forms": len(forms),
        "surveys": len(surveys),
        "campaigns": len(campaigns),
        "funnels": len(funnels),
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tab_id": tab_id,
        "location": {
            "id": str(location.id),
            "slug": location.slug,
            "name": location.name,
            "ghl_location_id": location.ghl_location_id,
        },
        "summary": summary,
        "items": plan_items,
    }


async def execute_browser_export_plan(
    plan: dict[str, Any],
    profile_name: str = "ghl_session",
    headless: bool = False,
    continue_on_error: bool = True,
) -> dict[str, Any]:
    """Execute a browser export plan with a persistent browser profile."""
    items = plan.get("items", [])
    if not isinstance(items, list):
        items = []

    summary: dict[str, Any] = {
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "profile_name": profile_name,
        "headless": headless,
        "continue_on_error": continue_on_error,
        "items_total": len(items),
        "items_completed": 0,
        "steps_total": sum(len(item.get("steps", [])) for item in items if isinstance(item, dict)),
        "steps_completed": 0,
        "errors": [],
        "results": [],
        "success": True,
        "aborted": False,
    }
    if not items:
        return summary

    browser_agent_cls = _get_browser_agent_cls()
    async with browser_agent_cls(
        profile_name=profile_name,
        headless=headless,
        capture_network=False,
    ) as agent:
        for item in items:
            if not isinstance(item, dict):
                continue

            domain = str(item.get("domain", "unknown"))
            name = str(item.get("name", "unnamed"))
            item_label = f"{domain}:{name}"
            steps = item.get("steps", [])
            if not isinstance(steps, list):
                steps = []

            item_result: dict[str, Any] = {
                "domain": domain,
                "name": name,
                "local_id": item.get("local_id"),
                "steps_total": len(steps),
                "steps_completed": 0,
                "errors": [],
                "success": True,
            }

            for index, step in enumerate(steps):
                if not isinstance(step, dict):
                    continue

                step_name = str(step.get("name", f"step_{index + 1}"))
                required = bool(step.get("required", True))
                command = step.get("command", {})

                exec_result = await _execute_step_command(
                    agent,
                    step_name=f"{item_label}_{step_name}",
                    command=command if isinstance(command, dict) else {},
                )

                if exec_result.get("success"):
                    item_result["steps_completed"] += 1
                    summary["steps_completed"] += 1

                    wait_after = _parse_wait(step.get("wait_after", 0))
                    if wait_after > 0:
                        await asyncio.sleep(wait_after)

                    if bool(step.get("screenshot_after", False)):
                        try:
                            await agent.screenshot(_safe_name(f"{item_label}_{step_name}_after"))
                        except Exception as exc:
                            screenshot_error = (
                                f"{item_label}:{step_name}: screenshot_after failed: {exc}"
                            )
                            item_result["errors"].append(screenshot_error)
                            summary["errors"].append(screenshot_error)
                    continue

                error = str(exec_result.get("error", "Unknown execution error"))
                failure = f"{item_label}:{step_name}: {error}"
                item_result["errors"].append(failure)
                summary["errors"].append(failure)

                if required:
                    item_result["success"] = False
                    if not continue_on_error:
                        item_result["aborted_at_step"] = step_name
                        summary["results"].append(item_result)
                        summary["success"] = False
                        summary["aborted"] = True
                        return summary
                    break

            if item_result["success"]:
                summary["items_completed"] += 1

            summary["results"].append(item_result)

    if summary["items_completed"] != summary["items_total"] or summary["errors"]:
        summary["success"] = False
    return summary


async def reconcile_browser_export_ids(
    db: AsyncSession,
    location: Location,
    ghl: Any,
    plan: dict[str, Any],
) -> SyncResult:
    """Reconcile locally-created records with remote IDs after UI export."""
    result = SyncResult()
    lid = location.ghl_location_id
    if not lid:
        result.errors.append("WARN: Browser fallback reconcile skipped (missing location GHL ID)")
        return result

    now = datetime.now(timezone.utc)

    form_ids = _target_ids(plan, "forms")
    if form_ids:
        forms = list(
            (
                await db.execute(
                    select(Form)
                    .where(Form.location_id == location.id)
                    .options(selectinload(Form.fields))
                )
            ).scalars()
        )
        forms = [f for f in forms if str(f.id) in form_ids]

        try:
            remote_forms = _extract_items(await ghl.forms.list(location_id=lid), "forms")
        except Exception as exc:
            remote_forms = []
            result.errors.append(f"Browser reconcile forms list failed: {exc}")

        forms_by_name: dict[str, dict[str, Any]] = {}
        for remote_form in remote_forms:
            key = _normalize_name(str(remote_form.get("name", "")))
            if key and key not in forms_by_name:
                forms_by_name[key] = remote_form

        for form in forms:
            remote_form = forms_by_name.get(_normalize_name(form.name))
            if not remote_form:
                continue

            remote_id = _extract_ghl_id(remote_form)
            if remote_id and form.ghl_id != remote_id:
                form.ghl_id = remote_id
                form.ghl_location_id = lid
                form.last_synced_at = now
                result.updated += 1

            if not remote_id:
                continue

            try:
                detail_payload = _extract_payload(_to_dict(await ghl.forms.get(remote_id)), "form")
            except Exception as exc:
                result.errors.append(f"Browser reconcile form detail failed ({form.name}): {exc}")
                continue

            remote_fields = _extract_form_fields(detail_payload, remote_form)
            remote_fields_by_label: dict[str, dict[str, Any]] = {}
            for remote_field in remote_fields:
                key = _normalize_name(
                    str(
                        remote_field.get("label")
                        or remote_field.get("name")
                        or remote_field.get("placeholder")
                        or ""
                    )
                )
                if key and key not in remote_fields_by_label:
                    remote_fields_by_label[key] = remote_field

            for index, local_field in enumerate(sorted(form.fields, key=lambda f: f.position)):
                remote_field = remote_fields_by_label.get(_normalize_name(local_field.label))
                if remote_field is None and index < len(remote_fields):
                    remote_field = remote_fields[index]

                if not isinstance(remote_field, dict):
                    continue

                remote_field_id = _extract_ghl_id(remote_field)
                if not remote_field_id:
                    continue

                options_json = (
                    dict(local_field.options_json)
                    if isinstance(local_field.options_json, dict)
                    else {}
                )
                if options_json.get("_ghl_field_id") != remote_field_id:
                    options_json["_ghl_field_id"] = remote_field_id
                    local_field.options_json = options_json
                    result.updated += 1

    survey_ids = _target_ids(plan, "surveys")
    if survey_ids:
        surveys = list(
            (
                await db.execute(
                    select(Survey)
                    .where(Survey.location_id == location.id)
                    .options(selectinload(Survey.questions))
                )
            ).scalars()
        )
        surveys = [s for s in surveys if str(s.id) in survey_ids]

        try:
            remote_surveys = _extract_items(await ghl.surveys.list(location_id=lid), "surveys")
        except Exception as exc:
            remote_surveys = []
            result.errors.append(f"Browser reconcile surveys list failed: {exc}")

        surveys_by_name: dict[str, dict[str, Any]] = {}
        for remote_survey in remote_surveys:
            key = _normalize_name(str(remote_survey.get("name", "")))
            if key and key not in surveys_by_name:
                surveys_by_name[key] = remote_survey

        for survey in surveys:
            remote_survey = surveys_by_name.get(_normalize_name(survey.name))
            if not remote_survey:
                continue

            remote_id = _extract_ghl_id(remote_survey)
            if remote_id and survey.ghl_id != remote_id:
                survey.ghl_id = remote_id
                survey.ghl_location_id = lid
                survey.last_synced_at = now
                result.updated += 1

            if not remote_id:
                continue

            try:
                detail_payload = _extract_payload(_to_dict(await ghl.surveys.get(remote_id)), "survey")
            except Exception as exc:
                result.errors.append(f"Browser reconcile survey detail failed ({survey.name}): {exc}")
                continue

            remote_questions = _extract_survey_questions(detail_payload, remote_survey)
            remote_questions_by_text: dict[str, dict[str, Any]] = {}
            for remote_question in remote_questions:
                key = _normalize_name(
                    str(
                        remote_question.get("question")
                        or remote_question.get("questionText")
                        or remote_question.get("label")
                        or ""
                    )
                )
                if key and key not in remote_questions_by_text:
                    remote_questions_by_text[key] = remote_question

            for index, local_question in enumerate(sorted(survey.questions, key=lambda q: q.position)):
                remote_question = remote_questions_by_text.get(
                    _normalize_name(local_question.question_text)
                )
                if remote_question is None and index < len(remote_questions):
                    remote_question = remote_questions[index]

                if not isinstance(remote_question, dict):
                    continue

                remote_question_id = _extract_ghl_id(remote_question)
                if not remote_question_id:
                    continue

                options_json = (
                    dict(local_question.options_json)
                    if isinstance(local_question.options_json, dict)
                    else {}
                )
                if options_json.get("_ghl_question_id") != remote_question_id:
                    options_json["_ghl_question_id"] = remote_question_id
                    local_question.options_json = options_json
                    result.updated += 1

    campaign_ids = _target_ids(plan, "campaigns")
    if campaign_ids:
        campaigns = list(
            (
                await db.execute(
                    select(Campaign).where(
                        Campaign.location_id == location.id
                    )
                )
            ).scalars()
        )
        campaigns = [c for c in campaigns if str(c.id) in campaign_ids]

        try:
            remote_campaigns = _extract_items(await ghl.campaigns.list(location_id=lid), "campaigns")
        except Exception as exc:
            remote_campaigns = []
            result.errors.append(f"Browser reconcile campaigns list failed: {exc}")

        campaigns_by_name: dict[str, dict[str, Any]] = {}
        for remote_campaign in remote_campaigns:
            key = _normalize_name(str(remote_campaign.get("name", "")))
            if key and key not in campaigns_by_name:
                campaigns_by_name[key] = remote_campaign

        for campaign in campaigns:
            remote_campaign = campaigns_by_name.get(_normalize_name(campaign.name))
            if not remote_campaign:
                continue
            remote_id = _extract_ghl_id(remote_campaign)
            if remote_id and campaign.ghl_id != remote_id:
                campaign.ghl_id = remote_id
                campaign.ghl_location_id = lid
                campaign.last_synced_at = now
                result.updated += 1

    funnel_ids = _target_ids(plan, "funnels")
    if funnel_ids:
        funnels = list(
            (
                await db.execute(
                    select(Funnel)
                    .where(Funnel.location_id == location.id)
                    .options(selectinload(Funnel.pages))
                )
            ).scalars()
        )
        funnels = [f for f in funnels if str(f.id) in funnel_ids]

        try:
            remote_funnels = _extract_items(await ghl.funnels.list(location_id=lid), "funnels")
        except Exception as exc:
            remote_funnels = []
            result.errors.append(f"Browser reconcile funnels list failed: {exc}")

        funnels_by_name: dict[str, dict[str, Any]] = {}
        for remote_funnel in remote_funnels:
            key = _normalize_name(str(remote_funnel.get("name", "")))
            if key and key not in funnels_by_name:
                funnels_by_name[key] = remote_funnel

        for funnel in funnels:
            remote_funnel = funnels_by_name.get(_normalize_name(funnel.name))
            if not remote_funnel:
                continue

            remote_id = _extract_ghl_id(remote_funnel)
            if remote_id and funnel.ghl_id != remote_id:
                funnel.ghl_id = remote_id
                funnel.ghl_location_id = lid
                funnel.last_synced_at = now
                result.updated += 1

            if not remote_id:
                continue

            try:
                remote_pages = _extract_items(
                    await ghl.funnels.pages(
                        remote_id,
                        location_id=lid,
                        limit=200,
                        offset=0,
                    ),
                    "pages",
                )
            except Exception as exc:
                remote_pages = []
                result.errors.append(f"Browser reconcile funnel pages failed ({funnel.name}): {exc}")

            pages_by_slug: dict[str, dict[str, Any]] = {}
            pages_by_name: dict[str, dict[str, Any]] = {}
            for remote_page in remote_pages:
                slug = remote_page.get("slug", remote_page.get("path", remote_page.get("urlSlug", "")))
                slug_key = _normalize_name(str(slug))
                if slug_key and slug_key not in pages_by_slug:
                    pages_by_slug[slug_key] = remote_page

                name_key = _normalize_name(str(remote_page.get("name", "")))
                if name_key and name_key not in pages_by_name:
                    pages_by_name[name_key] = remote_page

            for local_page in sorted(funnel.pages, key=lambda p: p.position):
                remote_page = pages_by_slug.get(_normalize_name(local_page.url_slug))
                if remote_page is None:
                    remote_page = pages_by_name.get(_normalize_name(local_page.name))
                if not remote_page:
                    continue

                remote_page_id = _extract_ghl_id(remote_page)
                if remote_page_id and local_page.ghl_id != remote_page_id:
                    local_page.ghl_id = remote_page_id
                    result.updated += 1

    await db.commit()
    return result


async def export_browser_backed_resources(
    db: AsyncSession,
    location: Location,
    tab_id: int = 0,
    execute: bool = False,
    profile_name: str = "ghl_session",
    headless: bool = False,
    continue_on_error: bool = True,
    ghl: Any | None = None,
) -> SyncResult:
    """Generate/execute browser fallback steps for unsupported resources."""
    result = SyncResult()

    plan = await build_browser_export_plan(db, location, tab_id=tab_id)
    items = plan.get("items", [])
    if not isinstance(items, list) or not items:
        return result

    archive_key = location.ghl_location_id or location.slug
    plan_path = write_sync_archive(archive_key, "browser_export_plan", plan)
    if plan_path:
        result.errors.append(
            f"INFO: Browser fallback plan generated at {plan_path} ({len(items)} resources)"
        )
    else:
        result.errors.append(
            f"INFO: Browser fallback plan generated for {len(items)} resources (archive write failed)"
        )

    if not execute:
        result.skipped = len(items)
        return result

    execution = await execute_browser_export_plan(
        plan,
        profile_name=profile_name,
        headless=headless,
        continue_on_error=continue_on_error,
    )
    execution_path = write_sync_archive(archive_key, "browser_export_execution", execution)
    items_total = int(execution.get("items_total", len(items)))
    items_completed = int(execution.get("items_completed", 0))
    result.created += items_completed
    result.skipped += max(items_total - items_completed, 0)

    if execution_path:
        result.errors.append(
            f"INFO: Browser fallback execution archived at {execution_path}"
        )
    if execution.get("success"):
        result.errors.append(
            f"INFO: Browser fallback execution completed ({items_completed}/{items_total})"
        )
    else:
        result.errors.append(
            f"WARN: Browser fallback execution incomplete ({items_completed}/{items_total})"
        )
        for err in execution.get("errors", []):
            if isinstance(err, str):
                result.errors.append(f"Browser fallback: {err}")

    if ghl is None:
        result.errors.append("WARN: Browser fallback ID reconciliation skipped (no GHL client)")
        return result

    reconcile_result = await reconcile_browser_export_ids(db, location, ghl, plan)
    result.updated += reconcile_result.updated
    result.errors.extend(reconcile_result.errors)

    reconciliation_summary = {
        "updated": reconcile_result.updated,
        "errors": reconcile_result.errors,
    }
    reconciliation_path = write_sync_archive(
        archive_key,
        "browser_export_reconciliation",
        reconciliation_summary,
    )
    if reconciliation_path:
        result.errors.append(
            f"INFO: Browser fallback reconciliation archived at {reconciliation_path}"
        )
    if reconcile_result.updated:
        result.errors.append(
            f"INFO: Browser fallback reconciled {reconcile_result.updated} local records"
        )

    return result
