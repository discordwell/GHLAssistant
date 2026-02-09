"""Tests for browser UI fallback task generation."""

from __future__ import annotations

from maxlevel.browser.chrome_mcp.tasks import GHLBrowserTasks, TaskStep


def _find_step(steps: list[TaskStep], name: str) -> TaskStep:
    for step in steps:
        if step.name == name:
            return step
    raise AssertionError(f"Missing step: {name}")


def test_create_form_via_ui_generates_expected_steps(mock_tab_id):
    tasks = GHLBrowserTasks(tab_id=mock_tab_id)
    steps = tasks.create_form_via_ui("Lead Form", description="New lead intake", is_active=False)

    navigate = _find_step(steps, "navigate_forms")
    assert navigate.command["tool"] == "mcp__claude-in-chrome__navigate"
    assert "sites/forms" in navigate.command["params"]["url"]
    assert navigate.command["params"]["tabId"] == mock_tab_id

    assert _find_step(steps, "set_form_inactive")
    assert _find_step(steps, "save_form")
    assert _find_step(steps, "verify_form_saved")


def test_add_form_field_via_ui_includes_required_toggle(mock_tab_id):
    tasks = GHLBrowserTasks(tab_id=mock_tab_id)
    steps = tasks.add_form_field_via_ui(
        form_name="Lead Form",
        label="Email",
        field_type="email",
        required=True,
    )

    choose_type = _find_step(steps, "choose_field_type")
    assert "email" in choose_type.description.lower()
    assert _find_step(steps, "set_field_required")


def test_create_survey_and_question_tasks(mock_tab_id):
    tasks = GHLBrowserTasks(tab_id=mock_tab_id)
    survey_steps = tasks.create_survey_via_ui("CSAT", "Post-call survey", is_active=True)
    question_steps = tasks.add_survey_question_via_ui(
        survey_name="CSAT",
        question_text="How was your experience?",
        question_type="rating",
        required=True,
    )

    navigate = _find_step(survey_steps, "navigate_surveys")
    assert "sites/surveys" in navigate.command["params"]["url"]
    assert _find_step(question_steps, "choose_question_type")
    assert _find_step(question_steps, "set_question_required")


def test_create_campaign_and_steps_tasks(mock_tab_id):
    tasks = GHLBrowserTasks(tab_id=mock_tab_id)
    campaign_steps = tasks.create_campaign_via_ui(
        "Welcome Campaign",
        description="Onboarding campaign",
        status="active",
    )
    step_steps = tasks.add_campaign_step_via_ui(
        campaign_name="Welcome Campaign",
        step_type="email",
        subject="Welcome!",
        body="Thanks for joining",
        delay_minutes=30,
    )

    navigate = _find_step(campaign_steps, "navigate_campaigns")
    assert "marketing/campaigns" in navigate.command["params"]["url"]
    assert _find_step(campaign_steps, "set_campaign_status")
    assert _find_step(step_steps, "set_campaign_step_delay")
    assert _find_step(step_steps, "save_campaign_step")


def test_create_funnel_and_page_tasks(mock_tab_id):
    tasks = GHLBrowserTasks(tab_id=mock_tab_id)
    funnel_steps = tasks.create_funnel_via_ui(
        name="Main Funnel",
        description="Primary conversion flow",
        is_published=True,
    )
    page_steps = tasks.add_funnel_page_via_ui(
        funnel_name="Main Funnel",
        page_name="Landing",
        url_slug="landing",
        is_published=True,
    )

    navigate = _find_step(funnel_steps, "navigate_funnels")
    assert "sites/funnels" in navigate.command["params"]["url"]
    assert _find_step(funnel_steps, "publish_funnel")
    assert _find_step(page_steps, "publish_funnel_page")
    assert _find_step(page_steps, "save_funnel_page")


def test_create_pipeline_and_stage_tasks(mock_tab_id):
    tasks = GHLBrowserTasks(tab_id=mock_tab_id)

    pipeline_steps = tasks.create_pipeline_via_ui(
        name="Sales Pipeline",
        description="Primary sales pipeline",
        is_active=True,
    )
    stage_steps = tasks.add_pipeline_stage_via_ui(
        pipeline_name="Sales Pipeline",
        stage_name="New Lead",
    )

    navigate = _find_step(pipeline_steps, "navigate_pipelines")
    assert navigate.command["tool"] == "mcp__claude-in-chrome__navigate"
    assert "opportunities/pipelines" in navigate.command["params"]["url"]
    assert _find_step(pipeline_steps, "save_pipeline")
    assert _find_step(stage_steps, "find_add_stage")


def test_create_workflow_via_ui_generates_expected_steps(mock_tab_id):
    tasks = GHLBrowserTasks(tab_id=mock_tab_id)
    steps = tasks.create_workflow_via_ui(
        name="Test Workflow",
        trigger="manual",
        status="draft",
    )

    navigate = _find_step(steps, "navigate_automations")
    assert navigate.command["tool"] == "mcp__claude-in-chrome__navigate"
    assert "automations" in navigate.command["params"]["url"]
    assert navigate.command["params"]["tabId"] == mock_tab_id

    set_name = _find_step(steps, "set_workflow_name")
    assert set_name.command["tool"] == "mcp__claude-in-chrome__form_input"
    assert set_name.command["params"]["value"] == "Test Workflow"

    assert _find_step(steps, "find_trigger_block")
    assert _find_step(steps, "find_save_workflow")


def test_workflow_action_steps_include_prefix(mock_tab_id):
    tasks = GHLBrowserTasks(tab_id=mock_tab_id)

    sms_steps = tasks.add_workflow_action_send_sms_via_ui("Hello", step_index=2)
    assert _find_step(sms_steps, "wf_step_002_find_add_action")
    assert _find_step(sms_steps, "wf_step_002_select_send_sms")

    delay_steps = tasks.add_workflow_delay_via_ui(120, step_index=3)
    assert _find_step(delay_steps, "wf_step_003_select_wait")
