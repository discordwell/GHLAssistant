"""Tests for Hiring Funnel CLI commands."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from maxlevel.cli import app
from tests.conftest import SAMPLE_LOCATION_ID, SAMPLE_CONTACT_ID


# ============================================================================
# Mock Data
# ============================================================================

MOCK_PIPELINE = {
    "id": "pipe_hiring_001",
    "_id": "pipe_hiring_001",
    "name": "Hiring Pipeline",
    "stages": [
        {"id": "stage_applied", "_id": "stage_applied", "name": "Applied", "position": 0},
        {"id": "stage_screening", "_id": "stage_screening", "name": "Screening", "position": 1},
        {"id": "stage_interview", "_id": "stage_interview", "name": "Phone Interview", "position": 2},
        {"id": "stage_offer", "_id": "stage_offer", "name": "Offer", "position": 3},
        {"id": "stage_hired", "_id": "stage_hired", "name": "Hired", "position": 4},
        {"id": "stage_rejected", "_id": "stage_rejected", "name": "Rejected", "position": 5},
    ],
}

MOCK_OPPORTUNITY = {
    "id": "opp_001",
    "_id": "opp_001",
    "name": "John Doe - Engineer",
    "pipelineId": "pipe_hiring_001",
    "pipelineStageId": "stage_applied",
    "contactId": SAMPLE_CONTACT_ID,
    "status": "open",
    "monetaryValue": 0,
}

MOCK_CONTACT = {
    "contact": {
        "id": SAMPLE_CONTACT_ID,
        "firstName": "John",
        "lastName": "Doe",
        "email": "john@example.com",
        "tags": ["applicant"],
    }
}


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def hiring_mock_client():
    """Mock GHLClient with hiring-specific API responses."""
    mock_client = MagicMock()
    mock_client.config = MagicMock()
    mock_client.config.location_id = SAMPLE_LOCATION_ID

    # Contacts API
    mock_client.contacts = AsyncMock()
    mock_client.contacts.create = AsyncMock(return_value=MOCK_CONTACT)
    mock_client.contacts.add_tag = AsyncMock(return_value={"succeeded": True})
    mock_client.contacts.remove_tag = AsyncMock(return_value={"succeeded": True})
    mock_client.contacts.add_note = AsyncMock(return_value={"note": {"id": "note_001"}})
    mock_client.contacts.update = AsyncMock(return_value=MOCK_CONTACT)

    # Opportunities API
    mock_client.opportunities = AsyncMock()
    mock_client.opportunities.pipelines = AsyncMock(return_value={
        "pipelines": [MOCK_PIPELINE],
    })
    mock_client.opportunities.list = AsyncMock(return_value={
        "opportunities": [MOCK_OPPORTUNITY],
        "total": 1,
    })
    mock_client.opportunities.get = AsyncMock(return_value={
        "opportunity": MOCK_OPPORTUNITY,
    })
    mock_client.opportunities.create = AsyncMock(return_value={
        "opportunity": MOCK_OPPORTUNITY,
    })
    mock_client.opportunities.move_stage = AsyncMock(return_value={
        "opportunity": {**MOCK_OPPORTUNITY, "pipelineStageId": "stage_screening"},
    })
    mock_client.opportunities.mark_won = AsyncMock(return_value={
        "opportunity": {**MOCK_OPPORTUNITY, "status": "won"},
    })
    mock_client.opportunities.mark_lost = AsyncMock(return_value={
        "opportunity": {**MOCK_OPPORTUNITY, "status": "lost"},
    })

    # Tags API (for provision)
    mock_client.tags = AsyncMock()
    mock_client.tags.list = AsyncMock(return_value={"tags": []})
    mock_client.tags.create = AsyncMock(return_value={"tag": {"id": "tag_001", "name": "test"}})

    # Custom fields API
    mock_client.custom_fields = AsyncMock()
    mock_client.custom_fields.list = AsyncMock(return_value={"customFields": []})
    mock_client.custom_fields.create = AsyncMock(return_value={"customField": {"id": "cf_001"}})

    # Custom values API
    mock_client.custom_values = AsyncMock()
    mock_client.custom_values.list = AsyncMock(return_value={"customValues": []})
    mock_client.custom_values.create = AsyncMock(return_value={"customValue": {"id": "cv_001"}})

    # Conversation AI API
    mock_client.conversation_ai = AsyncMock()
    mock_client.conversation_ai.create_agent = AsyncMock(return_value={
        "agent": {"id": "agent_hiring_001", "name": "Hiring Screener"},
    })

    # Snapshot APIs (for audit)
    mock_client.workflows = AsyncMock()
    mock_client.workflows.list = AsyncMock(return_value={"workflows": []})
    mock_client.calendars = AsyncMock()
    mock_client.calendars.list = AsyncMock(return_value={"calendars": []})
    mock_client.forms = AsyncMock()
    mock_client.forms.list = AsyncMock(return_value={"forms": []})
    mock_client.surveys = AsyncMock()
    mock_client.surveys.list = AsyncMock(return_value={"surveys": []})
    mock_client.campaigns = AsyncMock()
    mock_client.campaigns.list = AsyncMock(return_value={"campaigns": []})
    mock_client.funnels = AsyncMock()
    mock_client.funnels.list = AsyncMock(return_value={"funnels": []})

    return mock_client


@pytest.fixture
def hiring_client_factory(hiring_mock_client):
    """Create factory for mock GHLClient context managers."""
    def _create():
        mock_instance = MagicMock()
        mock_instance.__aenter__ = AsyncMock(return_value=hiring_mock_client)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        return mock_instance
    return _create


# ============================================================================
# Tests
# ============================================================================

class TestHiringSetup:
    """Tests for 'maxlevel hiring setup' command."""

    def test_setup_dry_run(self, cli_runner, hiring_mock_client, hiring_client_factory):
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = hiring_client_factory()
            result = cli_runner.invoke(app, ["hiring", "setup"])

            assert result.exit_code == 0
            assert "dry run" in result.output.lower()

    def test_setup_apply(self, cli_runner, hiring_mock_client, hiring_client_factory):
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = hiring_client_factory()
            result = cli_runner.invoke(app, ["hiring", "setup", "--apply"])

            assert result.exit_code == 0
            hiring_mock_client.conversation_ai.create_agent.assert_called_once()

    def test_setup_with_role(self, cli_runner, hiring_mock_client, hiring_client_factory):
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = hiring_client_factory()
            result = cli_runner.invoke(app, ["hiring", "setup", "--role", "Engineer"])

            assert result.exit_code == 0

    def test_setup_with_custom_stages(self, cli_runner, hiring_mock_client, hiring_client_factory):
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = hiring_client_factory()
            result = cli_runner.invoke(app, [
                "hiring", "setup",
                "--stages", "Applied,Screen,Offer,Hired,Rejected",
            ])

            assert result.exit_code == 0

    def test_setup_export_yaml(self, cli_runner, tmp_path):
        output_path = str(tmp_path / "hiring.yaml")
        result = cli_runner.invoke(app, ["hiring", "setup", "--output", output_path])

        assert result.exit_code == 0
        assert "exported" in result.output.lower()
        assert (tmp_path / "hiring.yaml").exists()


class TestHiringAddApplicant:
    """Tests for 'maxlevel hiring add-applicant' command."""

    def test_add_applicant_minimal(self, cli_runner, hiring_mock_client, hiring_client_factory):
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = hiring_client_factory()
            result = cli_runner.invoke(app, ["hiring", "add-applicant", "John", "Doe"])

            assert result.exit_code == 0
            assert "created" in result.output.lower()
            hiring_mock_client.contacts.create.assert_called_once()

    def test_add_applicant_full(self, cli_runner, hiring_mock_client, hiring_client_factory):
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = hiring_client_factory()
            result = cli_runner.invoke(app, [
                "hiring", "add-applicant", "Jane", "Smith",
                "--email", "jane@example.com",
                "--phone", "+15551234567",
                "--position", "Engineer",
                "--resume", "https://example.com/resume.pdf",
                "--salary", "100000",
                "--source", "LinkedIn",
            ])

            assert result.exit_code == 0
            assert "created" in result.output.lower()
            # Verify contact was created with all fields
            call_kwargs = hiring_mock_client.contacts.create.call_args
            assert call_kwargs[1]["first_name"] == "Jane"
            assert call_kwargs[1]["last_name"] == "Smith"
            assert call_kwargs[1]["email"] == "jane@example.com"
            assert call_kwargs[1]["tags"] == ["applicant"]

    def test_add_applicant_creates_opportunity(self, cli_runner, hiring_mock_client, hiring_client_factory):
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = hiring_client_factory()
            result = cli_runner.invoke(app, [
                "hiring", "add-applicant", "John", "Doe",
                "--position", "Engineer",
            ])

            assert result.exit_code == 0
            hiring_mock_client.opportunities.create.assert_called_once()
            assert "Opportunity ID" in result.output

    def test_add_applicant_json(self, cli_runner, hiring_mock_client, hiring_client_factory):
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = hiring_client_factory()
            result = cli_runner.invoke(app, [
                "hiring", "add-applicant", "John", "Doe", "--json",
            ])

            assert result.exit_code == 0
            assert '"contact"' in result.output


class TestHiringList:
    """Tests for 'maxlevel hiring list' command."""

    def test_list_applicants(self, cli_runner, hiring_mock_client, hiring_client_factory):
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = hiring_client_factory()
            result = cli_runner.invoke(app, ["hiring", "list"])

            assert result.exit_code == 0
            assert "Hiring Pipeline Applicants" in result.output
            assert "John Doe" in result.output

    def test_list_with_stage_filter(self, cli_runner, hiring_mock_client, hiring_client_factory):
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = hiring_client_factory()
            result = cli_runner.invoke(app, ["hiring", "list", "--stage", "Applied"])

            assert result.exit_code == 0
            hiring_mock_client.opportunities.list.assert_called_once()

    def test_list_no_pipeline(self, cli_runner, hiring_mock_client, hiring_client_factory):
        hiring_mock_client.opportunities.pipelines = AsyncMock(return_value={"pipelines": []})

        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = hiring_client_factory()
            result = cli_runner.invoke(app, ["hiring", "list"])

            assert result.exit_code != 0 or "No hiring pipeline found" in result.output

    def test_list_json(self, cli_runner, hiring_mock_client, hiring_client_factory):
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = hiring_client_factory()
            result = cli_runner.invoke(app, ["hiring", "list", "--json"])

            assert result.exit_code == 0
            assert '"opportunities"' in result.output


class TestHiringAdvance:
    """Tests for 'maxlevel hiring advance' command."""

    def test_advance_to_next_stage(self, cli_runner, hiring_mock_client, hiring_client_factory):
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = hiring_client_factory()
            result = cli_runner.invoke(app, ["hiring", "advance", "opp_001"])

            assert result.exit_code == 0
            assert "Moved to stage" in result.output
            hiring_mock_client.opportunities.move_stage.assert_called_once_with(
                "opp_001", "stage_screening"
            )

    def test_advance_to_named_stage(self, cli_runner, hiring_mock_client, hiring_client_factory):
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = hiring_client_factory()
            result = cli_runner.invoke(app, ["hiring", "advance", "opp_001", "--stage", "Offer"])

            assert result.exit_code == 0
            assert "Moved to stage" in result.output
            hiring_mock_client.opportunities.move_stage.assert_called_once_with(
                "opp_001", "stage_offer"
            )

    def test_advance_adds_interview_tag(self, cli_runner, hiring_mock_client, hiring_client_factory):
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = hiring_client_factory()
            result = cli_runner.invoke(app, [
                "hiring", "advance", "opp_001", "--stage", "Phone Interview",
            ])

            assert result.exit_code == 0
            hiring_mock_client.contacts.add_tag.assert_any_call(
                SAMPLE_CONTACT_ID, "interview-scheduled"
            )

    def test_advance_invalid_stage(self, cli_runner, hiring_mock_client, hiring_client_factory):
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = hiring_client_factory()
            result = cli_runner.invoke(app, [
                "hiring", "advance", "opp_001", "--stage", "Nonexistent",
            ])

            assert result.exit_code != 0 or "not found" in result.output.lower()


class TestHiringReject:
    """Tests for 'maxlevel hiring reject' command."""

    def test_reject_applicant(self, cli_runner, hiring_mock_client, hiring_client_factory):
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = hiring_client_factory()
            result = cli_runner.invoke(app, ["hiring", "reject", "opp_001"])

            assert result.exit_code == 0
            assert "rejected" in result.output.lower()
            hiring_mock_client.opportunities.mark_lost.assert_called_once_with("opp_001")

    def test_reject_moves_to_rejected_stage(self, cli_runner, hiring_mock_client, hiring_client_factory):
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = hiring_client_factory()
            cli_runner.invoke(app, ["hiring", "reject", "opp_001"])

            hiring_mock_client.opportunities.move_stage.assert_called_once_with(
                "opp_001", "stage_rejected"
            )

    def test_reject_updates_tags(self, cli_runner, hiring_mock_client, hiring_client_factory):
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = hiring_client_factory()
            cli_runner.invoke(app, ["hiring", "reject", "opp_001"])

            hiring_mock_client.contacts.add_tag.assert_any_call(
                SAMPLE_CONTACT_ID, "rejected"
            )
            hiring_mock_client.contacts.remove_tag.assert_any_call(
                SAMPLE_CONTACT_ID, "applicant"
            )

    def test_reject_with_reason(self, cli_runner, hiring_mock_client, hiring_client_factory):
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = hiring_client_factory()
            result = cli_runner.invoke(app, [
                "hiring", "reject", "opp_001", "--reason", "Not enough experience",
            ])

            assert result.exit_code == 0
            assert "Not enough experience" in result.output
            hiring_mock_client.contacts.add_note.assert_called_once_with(
                SAMPLE_CONTACT_ID, "Rejection reason: Not enough experience"
            )


class TestHiringHire:
    """Tests for 'maxlevel hiring hire' command."""

    def test_hire_applicant(self, cli_runner, hiring_mock_client, hiring_client_factory):
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = hiring_client_factory()
            result = cli_runner.invoke(app, ["hiring", "hire", "opp_001"])

            assert result.exit_code == 0
            assert "hired" in result.output.lower()
            hiring_mock_client.opportunities.mark_won.assert_called_once_with("opp_001")

    def test_hire_moves_to_hired_stage(self, cli_runner, hiring_mock_client, hiring_client_factory):
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = hiring_client_factory()
            cli_runner.invoke(app, ["hiring", "hire", "opp_001"])

            hiring_mock_client.opportunities.move_stage.assert_called_once_with(
                "opp_001", "stage_hired"
            )

    def test_hire_updates_tags(self, cli_runner, hiring_mock_client, hiring_client_factory):
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = hiring_client_factory()
            cli_runner.invoke(app, ["hiring", "hire", "opp_001"])

            hiring_mock_client.contacts.add_tag.assert_any_call(
                SAMPLE_CONTACT_ID, "hired"
            )
            hiring_mock_client.contacts.remove_tag.assert_any_call(
                SAMPLE_CONTACT_ID, "applicant"
            )

    def test_hire_with_start_date_and_salary(self, cli_runner, hiring_mock_client, hiring_client_factory):
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = hiring_client_factory()
            result = cli_runner.invoke(app, [
                "hiring", "hire", "opp_001",
                "--start-date", "2026-03-01",
                "--salary", "120000",
            ])

            assert result.exit_code == 0
            assert "2026-03-01" in result.output
            assert "$120,000.00" in result.output
            # Verify custom fields updated
            hiring_mock_client.contacts.update.assert_called_once()


class TestHiringStatus:
    """Tests for 'maxlevel hiring status' command."""

    def test_status_dashboard(self, cli_runner, hiring_mock_client, hiring_client_factory):
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = hiring_client_factory()
            result = cli_runner.invoke(app, ["hiring", "status"])

            assert result.exit_code == 0
            assert "Hiring Dashboard" in result.output
            assert "Applicants by Stage" in result.output

    def test_status_no_pipeline(self, cli_runner, hiring_mock_client, hiring_client_factory):
        hiring_mock_client.opportunities.pipelines = AsyncMock(return_value={"pipelines": []})

        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = hiring_client_factory()
            result = cli_runner.invoke(app, ["hiring", "status"])

            assert result.exit_code != 0 or "No hiring pipeline found" in result.output

    def test_status_json(self, cli_runner, hiring_mock_client, hiring_client_factory):
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = hiring_client_factory()
            result = cli_runner.invoke(app, ["hiring", "status", "--json"])

            assert result.exit_code == 0
            assert '"stage_counts"' in result.output
            assert '"total"' in result.output


class TestHiringAudit:
    """Tests for 'maxlevel hiring audit' command."""

    def test_audit_runs(self, cli_runner, hiring_mock_client, hiring_client_factory):
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = hiring_client_factory()
            result = cli_runner.invoke(app, ["hiring", "audit"])

            assert result.exit_code == 0

    def test_audit_json(self, cli_runner, hiring_mock_client, hiring_client_factory):
        with patch("maxlevel.api.GHLClient") as MockClient:
            MockClient.from_session.return_value = hiring_client_factory()
            result = cli_runner.invoke(app, ["hiring", "audit", "--json"])

            assert result.exit_code == 0
            assert '"compliance_score"' in result.output


class TestHiringHelp:
    """Tests for hiring command help output."""

    def test_hiring_help(self, cli_runner):
        result = cli_runner.invoke(app, ["hiring", "--help"])

        assert result.exit_code == 0
        assert "setup" in result.output
        assert "add-applicant" in result.output
        assert "list" in result.output
        assert "advance" in result.output
        assert "reject" in result.output
        assert "hire" in result.output
        assert "status" in result.output
        assert "audit" in result.output
