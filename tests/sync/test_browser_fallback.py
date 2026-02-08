"""Tests for browser-backed fallback export planning."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from crm.models.base import Base
from crm.models.campaign import Campaign, CampaignStep
from crm.models.form import Form, FormField
from crm.models.funnel import Funnel, FunnelPage
from crm.models.location import Location
from crm.models.survey import Survey, SurveyQuestion
from crm.schemas.sync import SyncResult
from crm.sync.browser_fallback import (
    build_browser_export_plan,
    execute_browser_export_plan,
    export_browser_backed_resources,
    reconcile_browser_export_ids,
)


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def location(db: AsyncSession) -> Location:
    loc = Location(
        id=uuid.uuid4(),
        name="Test Location",
        slug="test-location",
        timezone="UTC",
        ghl_location_id="ghl_loc_123",
    )
    db.add(loc)
    await db.flush()

    form = Form(location_id=loc.id, name="Lead Form", ghl_id=None)
    db.add(form)
    await db.flush()
    db.add(FormField(form_id=form.id, label="Email", field_type="email", position=0))

    survey = Survey(location_id=loc.id, name="CSAT", ghl_id=None)
    db.add(survey)
    await db.flush()
    db.add(SurveyQuestion(survey_id=survey.id, question_text="How was it?", question_type="rating", position=0))

    campaign = Campaign(location_id=loc.id, name="Welcome", ghl_id=None)
    db.add(campaign)
    await db.flush()
    db.add(CampaignStep(campaign_id=campaign.id, step_type="email", position=0, subject="Welcome"))

    funnel = Funnel(location_id=loc.id, name="Main Funnel", ghl_id=None)
    db.add(funnel)
    await db.flush()
    db.add(FunnelPage(funnel_id=funnel.id, name="Landing", url_slug="landing", position=0))

    await db.commit()
    await db.refresh(loc)
    return loc


@pytest.mark.asyncio
async def test_build_browser_export_plan_includes_all_domains(db: AsyncSession, location: Location):
    plan = await build_browser_export_plan(db, location, tab_id=12345)

    assert plan["tab_id"] == 12345
    assert plan["location"]["ghl_location_id"] == "ghl_loc_123"
    assert plan["summary"]["forms"] == 1
    assert plan["summary"]["surveys"] == 1
    assert plan["summary"]["campaigns"] == 1
    assert plan["summary"]["funnels"] == 1

    items = plan["items"]
    assert len(items) == 4
    domains = {item["domain"] for item in items}
    assert domains == {"forms", "surveys", "campaigns", "funnels"}
    assert all(item["steps"] for item in items)


@pytest.mark.asyncio
async def test_export_browser_backed_resources_writes_archive(db: AsyncSession, location: Location, monkeypatch):
    captured = {}

    def fake_archive(location_key: str, domain: str, payload):
        captured["location_key"] = location_key
        captured["domain"] = domain
        captured["payload"] = payload
        return Path("/tmp/browser_plan.json")

    monkeypatch.setattr("crm.sync.browser_fallback.write_sync_archive", fake_archive)

    result = await export_browser_backed_resources(db, location, tab_id=12345)

    assert result.skipped == 4
    assert captured["location_key"] == "ghl_loc_123"
    assert captured["domain"] == "browser_export_plan"
    assert captured["payload"]["summary"]["forms"] == 1
    assert result.errors
    assert "Browser fallback plan generated" in result.errors[0]


class FakeBrowserAgent:
    last_instance: "FakeBrowserAgent | None" = None

    def __init__(self, profile_name: str, headless: bool, capture_network: bool):
        self.profile_name = profile_name
        self.headless = headless
        self.capture_network = capture_network
        self.calls: list[tuple[str, str]] = []
        FakeBrowserAgent.last_instance = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def navigate(self, url: str):
        self.calls.append(("navigate", url))
        return {"url": url}

    async def evaluate(self, js: str):
        self.calls.append(("evaluate", js))
        if "empty_query" in js and "no_match" in js:
            return {"found": True}
        if "active_not_typable" in js:
            return {"ok": True}
        if "const key =" in js:
            return {"ok": True}
        if "document.activeElement" in js and "click" in js:
            return {"ok": True}
        return {"ok": True}

    async def screenshot(self, name: str | None = None):
        self.calls.append(("screenshot", name or ""))
        return f"/tmp/{name or 'screenshot'}.png"

    async def is_logged_in(self):
        return True


@pytest.mark.asyncio
async def test_execute_browser_export_plan_dispatches_supported_commands(monkeypatch):
    monkeypatch.setattr(
        "crm.sync.browser_fallback._get_browser_agent_cls",
        lambda: FakeBrowserAgent,
    )

    plan = {
        "items": [
            {
                "domain": "forms",
                "name": "Lead Form",
                "local_id": "local_form_1",
                "steps": [
                    {
                        "name": "navigate",
                        "command": {
                            "tool": "mcp__claude-in-chrome__navigate",
                            "params": {"url": "https://app.gohighlevel.com/sites/forms"},
                        },
                        "required": True,
                        "wait_after": 0,
                    },
                    {
                        "name": "find_button",
                        "command": {
                            "tool": "mcp__claude-in-chrome__find",
                            "params": {"query": "create form button"},
                        },
                        "required": True,
                        "wait_after": 0,
                    },
                    {
                        "name": "type_name",
                        "command": {
                            "tool": "mcp__claude-in-chrome__computer",
                            "params": {"action": "type", "text": "Lead Form"},
                        },
                        "required": True,
                        "wait_after": 0,
                    },
                    {
                        "name": "press_enter",
                        "command": {
                            "tool": "mcp__claude-in-chrome__computer",
                            "params": {"action": "key", "text": "Enter"},
                        },
                        "required": True,
                        "wait_after": 0,
                    },
                    {
                        "name": "pause",
                        "command": {
                            "tool": "mcp__claude-in-chrome__computer",
                            "params": {"action": "wait", "duration": 0},
                        },
                        "required": True,
                        "wait_after": 0,
                    },
                    {
                        "name": "screenshot",
                        "command": {
                            "tool": "mcp__claude-in-chrome__computer",
                            "params": {"action": "screenshot"},
                        },
                        "required": True,
                        "wait_after": 0,
                    },
                ],
            }
        ]
    }

    summary = await execute_browser_export_plan(
        plan,
        profile_name="ghl_session",
        headless=True,
        continue_on_error=True,
    )

    assert summary["success"] is True
    assert summary["items_total"] == 1
    assert summary["items_completed"] == 1
    assert summary["steps_completed"] == 6

    agent = FakeBrowserAgent.last_instance
    assert agent is not None
    assert agent.profile_name == "ghl_session"
    assert agent.headless is True
    call_names = [name for name, _ in agent.calls]
    assert "navigate" in call_names
    assert "evaluate" in call_names
    assert "screenshot" in call_names


class RetryFindBrowserAgent(FakeBrowserAgent):
    def __init__(self, profile_name: str, headless: bool, capture_network: bool):
        super().__init__(profile_name, headless, capture_network)
        self.find_attempts = 0

    async def evaluate(self, js: str):
        self.calls.append(("evaluate", js))
        if "empty_query" in js and "no_match" in js:
            self.find_attempts += 1
            if self.find_attempts < 2:
                return {"found": False}
            return {"found": True}
        return {"ok": True}


class LoggedOutBrowserAgent(FakeBrowserAgent):
    async def is_logged_in(self):
        return False


class AutoLoginBrowserAgent(FakeBrowserAgent):
    def __init__(self, profile_name: str, headless: bool, capture_network: bool):
        super().__init__(profile_name, headless, capture_network)
        self._logged_in = False
        self.login_calls: list[tuple[str, int]] = []

    async def is_logged_in(self):
        return self._logged_in

    async def login_ghl(self, email: str, password: str, timeout_seconds: int = 120, url: str = ""):
        # Do not store password; just assert we were invoked.
        self.login_calls.append((email, timeout_seconds))
        self._logged_in = True
        return {"success": True}


@pytest.mark.asyncio
async def test_execute_browser_export_plan_retries_find(monkeypatch):
    monkeypatch.setattr(
        "crm.sync.browser_fallback._get_browser_agent_cls",
        lambda: RetryFindBrowserAgent,
    )

    plan = {
        "items": [
            {
                "domain": "forms",
                "name": "Lead Form",
                "local_id": "local_form_1",
                "steps": [
                    {
                        "name": "find_button",
                        "description": "Find create form button",
                        "command": {
                            "tool": "mcp__claude-in-chrome__find",
                            "params": {"query": "create form button"},
                        },
                        "required": True,
                        "wait_after": 0,
                    }
                ],
            }
        ]
    }

    summary = await execute_browser_export_plan(
        plan,
        profile_name="ghl_session",
        headless=True,
        continue_on_error=True,
        max_find_attempts=3,
        retry_wait_seconds=0,
    )

    assert summary["success"] is True
    assert summary["steps_completed"] == 1
    agent = RetryFindBrowserAgent.last_instance
    assert agent is not None
    assert agent.find_attempts == 2


@pytest.mark.asyncio
async def test_execute_browser_export_plan_captures_failure_screenshot(monkeypatch):
    monkeypatch.setattr(
        "crm.sync.browser_fallback._get_browser_agent_cls",
        lambda: FakeBrowserAgent,
    )

    plan = {
        "items": [
            {
                "domain": "forms",
                "name": "Lead Form",
                "local_id": "local_form_1",
                "steps": [
                    {
                        "name": "unsupported",
                        "command": {
                            "tool": "mcp__claude-in-chrome__computer",
                            "params": {"action": "unknown"},
                        },
                        "required": True,
                        "wait_after": 0,
                    }
                ],
            }
        ]
    }

    summary = await execute_browser_export_plan(
        plan,
        profile_name="ghl_session",
        headless=True,
        continue_on_error=True,
    )

    assert summary["success"] is False
    assert summary["items_completed"] == 0
    assert summary["results"][0]["step_results"][0]["failure_screenshot"].startswith("/tmp/")


@pytest.mark.asyncio
async def test_execute_browser_export_plan_aborts_when_not_logged_in(monkeypatch):
    monkeypatch.setattr(
        "crm.sync.browser_fallback._get_browser_agent_cls",
        lambda: LoggedOutBrowserAgent,
    )

    plan = {
        "items": [
            {
                "domain": "forms",
                "name": "Lead Form",
                "local_id": "local_form_1",
                "steps": [],
            }
        ]
    }

    summary = await execute_browser_export_plan(
        plan,
        profile_name="ghl_session",
        headless=True,
        continue_on_error=True,
        require_login=True,
    )

    assert summary["success"] is False
    assert summary["aborted"] is True
    assert summary["preflight"]["logged_in"] is False
    assert any("not logged in" in msg.lower() for msg in summary["errors"])


@pytest.mark.asyncio
async def test_execute_browser_export_plan_attempts_auto_login(monkeypatch):
    monkeypatch.setattr(
        "crm.sync.browser_fallback._get_browser_agent_cls",
        lambda: AutoLoginBrowserAgent,
    )

    plan = {
        "items": [
            {
                "domain": "forms",
                "name": "Lead Form",
                "local_id": "local_form_1",
                "steps": [],
            }
        ]
    }

    summary = await execute_browser_export_plan(
        plan,
        profile_name="ghl_session",
        headless=True,
        continue_on_error=True,
        require_login=True,
        login_email="user@example.com",
        login_password="secret",
        login_timeout_seconds=5,
    )

    assert summary["success"] is True
    assert summary["items_completed"] == 1
    assert summary.get("preflight", {}).get("logged_in") is True
    agent = AutoLoginBrowserAgent.last_instance
    assert agent is not None
    assert agent.login_calls == [("user@example.com", 5)]

class FakeFormsAPI:
    async def list(self, location_id: str | None = None):
        return {"forms": [{"id": "ghl_form_remote", "name": "Lead Form"}]}

    async def get(self, form_id: str):
        return {
            "form": {
                "id": form_id,
                "name": "Lead Form",
                "fields": [{"id": "ghl_field_remote", "label": "Email"}],
            }
        }


class FakeSurveysAPI:
    async def list(self, location_id: str | None = None):
        return {"surveys": [{"id": "ghl_survey_remote", "name": "CSAT"}]}

    async def get(self, survey_id: str):
        return {
            "survey": {
                "id": survey_id,
                "name": "CSAT",
                "questions": [{"id": "ghl_question_remote", "questionText": "How was it?"}],
            }
        }


class FakeCampaignsAPI:
    async def list(self, location_id: str | None = None):
        return {"campaigns": [{"id": "ghl_campaign_remote", "name": "Welcome"}]}


class FakeFunnelsAPI:
    async def list(self, location_id: str | None = None):
        return {"funnels": [{"id": "ghl_funnel_remote", "name": "Main Funnel"}]}

    async def pages(
        self,
        funnel_id: str,
        limit: int = 50,
        offset: int = 0,
        location_id: str | None = None,
    ):
        return {"pages": [{"id": "ghl_page_remote", "name": "Landing", "path": "landing"}]}


class FakeGHL:
    def __init__(self):
        self.forms = FakeFormsAPI()
        self.surveys = FakeSurveysAPI()
        self.campaigns = FakeCampaignsAPI()
        self.funnels = FakeFunnelsAPI()


@pytest.mark.asyncio
async def test_reconcile_browser_export_ids_updates_local_records(db: AsyncSession, location: Location):
    plan = await build_browser_export_plan(db, location, tab_id=7)
    ghl = FakeGHL()

    result = await reconcile_browser_export_ids(db, location, ghl, plan)
    assert result.errors == []
    assert result.updated >= 7  # 4 parent records + field/question/page id mappings

    form = (await db.execute(select(Form))).scalar_one()
    field = (await db.execute(select(FormField))).scalar_one()
    survey = (await db.execute(select(Survey))).scalar_one()
    question = (await db.execute(select(SurveyQuestion))).scalar_one()
    campaign = (await db.execute(select(Campaign))).scalar_one()
    funnel = (await db.execute(select(Funnel))).scalar_one()
    page = (await db.execute(select(FunnelPage))).scalar_one()

    assert form.ghl_id == "ghl_form_remote"
    assert isinstance(field.options_json, dict)
    assert field.options_json.get("_ghl_field_id") == "ghl_field_remote"
    assert survey.ghl_id == "ghl_survey_remote"
    assert isinstance(question.options_json, dict)
    assert question.options_json.get("_ghl_question_id") == "ghl_question_remote"
    assert campaign.ghl_id == "ghl_campaign_remote"
    assert funnel.ghl_id == "ghl_funnel_remote"
    assert page.ghl_id == "ghl_page_remote"


@pytest.mark.asyncio
async def test_export_browser_backed_resources_execute_mode_aggregates_results(
    db: AsyncSession, location: Location, monkeypatch
):
    archived_domains: list[str] = []

    def fake_archive(location_key: str, domain: str, payload):
        archived_domains.append(domain)
        return Path(f"/tmp/{domain}.json")

    async def fake_execute(
        plan,
        profile_name,
        headless,
        continue_on_error,
        max_find_attempts,
        retry_wait_seconds,
        require_login,
        preflight_url,
        login_email,
        login_password,
        login_timeout_seconds,
    ):
        return {
            "success": True,
            "items_total": len(plan.get("items", [])),
            "items_completed": len(plan.get("items", [])),
            "errors": [],
        }

    async def fake_reconcile(db, location, ghl, plan, successful_ids_by_domain=None):
        return SyncResult(updated=3)

    monkeypatch.setattr("crm.sync.browser_fallback.write_sync_archive", fake_archive)
    monkeypatch.setattr("crm.sync.browser_fallback.execute_browser_export_plan", fake_execute)
    monkeypatch.setattr("crm.sync.browser_fallback.reconcile_browser_export_ids", fake_reconcile)

    result = await export_browser_backed_resources(
        db,
        location,
        tab_id=12345,
        execute=True,
        profile_name="ghl_session",
        headless=False,
        continue_on_error=True,
        ghl=object(),
    )

    assert result.created == 4
    assert result.updated == 3
    assert result.skipped == 0
    assert "browser_export_plan" in archived_domains
    assert "browser_export_execution" in archived_domains
    assert "browser_export_reconciliation" in archived_domains


@pytest.mark.asyncio
async def test_export_browser_backed_resources_skips_reconcile_without_successful_items(
    db: AsyncSession, location: Location, monkeypatch
):
    async def fake_execute(
        plan,
        profile_name,
        headless,
        continue_on_error,
        max_find_attempts,
        retry_wait_seconds,
        require_login,
        preflight_url,
        login_email,
        login_password,
        login_timeout_seconds,
    ):
        return {
            "success": False,
            "items_total": len(plan.get("items", [])),
            "items_completed": 0,
            "results": [],
            "errors": ["failed"],
        }

    async def fake_reconcile(db, location, ghl, plan, successful_ids_by_domain=None):
        raise AssertionError("reconcile should not be called when no items succeeded")

    monkeypatch.setattr("crm.sync.browser_fallback.execute_browser_export_plan", fake_execute)
    monkeypatch.setattr("crm.sync.browser_fallback.reconcile_browser_export_ids", fake_reconcile)

    result = await export_browser_backed_resources(
        db,
        location,
        tab_id=12345,
        execute=True,
        profile_name="ghl_session",
        headless=False,
        continue_on_error=True,
        ghl=object(),
    )

    assert result.created == 0
    assert result.updated == 0
    assert result.skipped == 4
    assert any("reconciliation skipped" in msg.lower() for msg in result.errors)
