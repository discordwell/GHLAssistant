"""Hiring funnel blueprint template definitions."""

from __future__ import annotations

from ..blueprint.models import (
    BlueprintMetadata,
    CustomFieldSpec,
    CustomValueSpec,
    LocationBlueprint,
    PipelineSpec,
    PipelineStageSpec,
    TagSpec,
)

DEFAULT_STAGES = [
    "Applied",
    "Screening",
    "Phone Interview",
    "In-Person Interview",
    "Background Check",
    "Offer",
    "Hired",
    "Rejected",
]

HIRING_TAGS = [
    TagSpec(name="applicant"),
    TagSpec(name="hired"),
    TagSpec(name="rejected"),
    TagSpec(name="interview-scheduled"),
    TagSpec(name="offer-extended"),
    TagSpec(name="screening"),
]

HIRING_CUSTOM_FIELDS = [
    CustomFieldSpec(
        name="Position Applied",
        field_key="contact.position_applied",
        data_type="TEXT",
        placeholder="e.g. Software Engineer",
    ),
    CustomFieldSpec(
        name="Resume URL",
        field_key="contact.resume_url",
        data_type="TEXT",
        placeholder="https://...",
    ),
    CustomFieldSpec(
        name="Desired Salary",
        field_key="contact.desired_salary",
        data_type="NUMERICAL",
    ),
    CustomFieldSpec(
        name="Available Start Date",
        field_key="contact.available_start_date",
        data_type="DATE",
    ),
    CustomFieldSpec(
        name="Referral Source",
        field_key="contact.referral_source",
        data_type="SINGLE_OPTIONS",
        placeholder="How did you hear about us?",
    ),
    CustomFieldSpec(
        name="Interview Score",
        field_key="contact.interview_score",
        data_type="NUMERICAL",
    ),
    CustomFieldSpec(
        name="Hiring Notes",
        field_key="contact.hiring_notes",
        data_type="LARGE_TEXT",
    ),
]

HIRING_CUSTOM_VALUES = [
    CustomValueSpec(
        name="hiring_email_template",
        value="Thank you for applying to {{contact.position_applied}}. We will review your application and get back to you shortly.",
    ),
    CustomValueSpec(
        name="interview_location",
        value="Main Office - Conference Room A",
    ),
]

SCREENING_AGENT_PROMPT = """You are a hiring screening assistant. Your role is to:

1. Greet applicants warmly and confirm their interest in the position.
2. Ask about their relevant experience and qualifications.
3. Ask about their availability and desired start date.
4. Ask about their salary expectations.
5. Ask how they heard about the position.
6. Thank them and let them know the hiring team will follow up.

Be professional, friendly, and concise. Do not make hiring decisions or promises.
If asked about specific role details you don't know, say the hiring manager will provide those details."""


def get_hiring_blueprint(
    role: str | None = None,
    stages: list[str] | None = None,
) -> LocationBlueprint:
    """Build a LocationBlueprint for a hiring funnel.

    Args:
        role: Optional role name for metadata description.
        stages: Custom pipeline stage names. Defaults to DEFAULT_STAGES.
    """
    stage_names = stages or DEFAULT_STAGES
    pipeline_stages = [
        PipelineStageSpec(name=s, position=i)
        for i, s in enumerate(stage_names)
    ]

    description = "Hiring funnel blueprint"
    if role:
        description = f"Hiring funnel blueprint for {role}"

    return LocationBlueprint(
        metadata=BlueprintMetadata(
            name="Hiring Funnel",
            description=description,
        ),
        tags=list(HIRING_TAGS),
        custom_fields=list(HIRING_CUSTOM_FIELDS),
        custom_values=list(HIRING_CUSTOM_VALUES),
        pipelines=[PipelineSpec(name="Hiring Pipeline", stages=pipeline_stages)],
    )
