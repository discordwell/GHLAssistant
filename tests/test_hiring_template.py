"""Tests for hiring funnel blueprint template."""

import pytest

from ghl_assistant.hiring.template import (
    DEFAULT_STAGES,
    HIRING_CUSTOM_FIELDS,
    HIRING_CUSTOM_VALUES,
    HIRING_TAGS,
    SCREENING_AGENT_PROMPT,
    get_hiring_blueprint,
)
from ghl_assistant.blueprint.models import (
    CustomFieldSpec,
    CustomValueSpec,
    LocationBlueprint,
    PipelineSpec,
    TagSpec,
)


class TestHiringTags:
    """Tests for hiring tag definitions."""

    def test_tag_count(self):
        assert len(HIRING_TAGS) == 6

    def test_all_tags_are_tagspec(self):
        for tag in HIRING_TAGS:
            assert isinstance(tag, TagSpec)

    def test_required_tags_present(self):
        names = {t.name for t in HIRING_TAGS}
        assert "applicant" in names
        assert "hired" in names
        assert "rejected" in names
        assert "interview-scheduled" in names
        assert "offer-extended" in names
        assert "screening" in names


class TestHiringCustomFields:
    """Tests for hiring custom field definitions."""

    def test_field_count(self):
        assert len(HIRING_CUSTOM_FIELDS) == 7

    def test_all_fields_are_customfieldspec(self):
        for cf in HIRING_CUSTOM_FIELDS:
            assert isinstance(cf, CustomFieldSpec)

    def test_field_keys_are_namespaced(self):
        for cf in HIRING_CUSTOM_FIELDS:
            assert cf.field_key.startswith("contact."), f"{cf.field_key} should start with 'contact.'"

    def test_position_applied_field(self):
        field = next(f for f in HIRING_CUSTOM_FIELDS if "position" in f.field_key)
        assert field.name == "Position Applied"
        assert field.data_type == "TEXT"

    def test_desired_salary_field(self):
        field = next(f for f in HIRING_CUSTOM_FIELDS if "salary" in f.field_key)
        assert field.name == "Desired Salary"
        assert field.data_type == "NUMERICAL"

    def test_start_date_field(self):
        field = next(f for f in HIRING_CUSTOM_FIELDS if "start_date" in f.field_key)
        assert field.data_type == "DATE"

    def test_referral_source_field(self):
        field = next(f for f in HIRING_CUSTOM_FIELDS if "referral" in f.field_key)
        assert field.data_type == "SINGLE_OPTIONS"

    def test_hiring_notes_field(self):
        field = next(f for f in HIRING_CUSTOM_FIELDS if "notes" in f.field_key)
        assert field.data_type == "LARGE_TEXT"


class TestHiringCustomValues:
    """Tests for hiring custom value definitions."""

    def test_value_count(self):
        assert len(HIRING_CUSTOM_VALUES) == 2

    def test_all_values_are_customvaluespec(self):
        for cv in HIRING_CUSTOM_VALUES:
            assert isinstance(cv, CustomValueSpec)

    def test_email_template_value(self):
        val = next(v for v in HIRING_CUSTOM_VALUES if "email" in v.name)
        assert "position_applied" in val.value

    def test_interview_location_value(self):
        val = next(v for v in HIRING_CUSTOM_VALUES if "interview" in v.name)
        assert len(val.value) > 0


class TestScreeningAgentPrompt:
    """Tests for the AI screening agent prompt."""

    def test_prompt_is_string(self):
        assert isinstance(SCREENING_AGENT_PROMPT, str)

    def test_prompt_mentions_screening(self):
        assert "screening" in SCREENING_AGENT_PROMPT.lower()

    def test_prompt_mentions_key_topics(self):
        lower = SCREENING_AGENT_PROMPT.lower()
        assert "experience" in lower
        assert "salary" in lower
        assert "availability" in lower or "start date" in lower


class TestDefaultStages:
    """Tests for default pipeline stages."""

    def test_stage_count(self):
        assert len(DEFAULT_STAGES) == 8

    def test_starts_with_applied(self):
        assert DEFAULT_STAGES[0] == "Applied"

    def test_ends_with_rejected(self):
        assert DEFAULT_STAGES[-1] == "Rejected"

    def test_hired_before_rejected(self):
        hired_idx = DEFAULT_STAGES.index("Hired")
        rejected_idx = DEFAULT_STAGES.index("Rejected")
        assert hired_idx < rejected_idx


class TestGetHiringBlueprint:
    """Tests for get_hiring_blueprint() function."""

    def test_returns_location_blueprint(self):
        bp = get_hiring_blueprint()
        assert isinstance(bp, LocationBlueprint)

    def test_default_metadata(self):
        bp = get_hiring_blueprint()
        assert bp.metadata.name == "Hiring Funnel"
        assert "Hiring funnel blueprint" in bp.metadata.description

    def test_metadata_with_role(self):
        bp = get_hiring_blueprint(role="Software Engineer")
        assert "Software Engineer" in bp.metadata.description

    def test_default_tags(self):
        bp = get_hiring_blueprint()
        assert len(bp.tags) == 6
        tag_names = {t.name for t in bp.tags}
        assert "applicant" in tag_names
        assert "hired" in tag_names

    def test_default_custom_fields(self):
        bp = get_hiring_blueprint()
        assert len(bp.custom_fields) == 7

    def test_default_custom_values(self):
        bp = get_hiring_blueprint()
        assert len(bp.custom_values) == 2

    def test_default_pipeline(self):
        bp = get_hiring_blueprint()
        assert len(bp.pipelines) == 1
        pipeline = bp.pipelines[0]
        assert pipeline.name == "Hiring Pipeline"
        assert len(pipeline.stages) == 8

    def test_pipeline_stages_have_positions(self):
        bp = get_hiring_blueprint()
        pipeline = bp.pipelines[0]
        for i, stage in enumerate(pipeline.stages):
            assert stage.position == i

    def test_custom_stages(self):
        custom = ["Applied", "Phone Screen", "Technical", "Offer", "Hired", "Rejected"]
        bp = get_hiring_blueprint(stages=custom)
        pipeline = bp.pipelines[0]
        assert len(pipeline.stages) == 6
        assert pipeline.stages[0].name == "Applied"
        assert pipeline.stages[1].name == "Phone Screen"
        assert pipeline.stages[2].name == "Technical"

    def test_blueprint_does_not_mutate_globals(self):
        bp1 = get_hiring_blueprint()
        bp1.tags.append(TagSpec(name="extra"))
        bp2 = get_hiring_blueprint()
        assert len(bp2.tags) == 6

    def test_provisionable_sections(self):
        bp = get_hiring_blueprint()
        provisionable = bp.provisionable_sections()
        assert "tags" in provisionable
        assert "custom_fields" in provisionable
        assert "custom_values" in provisionable
        assert "pipelines" not in provisionable

    def test_readonly_sections(self):
        bp = get_hiring_blueprint()
        readonly = bp.readonly_sections()
        assert "pipelines" in readonly
        assert "tags" not in readonly
