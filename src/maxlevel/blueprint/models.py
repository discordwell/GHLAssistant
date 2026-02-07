"""Blueprint data models - dataclass specs for location configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class ResourceAccess(Enum):
    """Whether a resource type can be auto-provisioned or is read-only."""
    FULL_CRUD = "full_crud"
    READ_ONLY = "read_only"


# Maps resource type names to their access level
RESOURCE_ACCESS = {
    "tags": ResourceAccess.FULL_CRUD,
    "custom_fields": ResourceAccess.FULL_CRUD,
    "custom_values": ResourceAccess.FULL_CRUD,
    "pipelines": ResourceAccess.READ_ONLY,
    "workflows": ResourceAccess.READ_ONLY,
    "calendars": ResourceAccess.READ_ONLY,
    "forms": ResourceAccess.READ_ONLY,
    "surveys": ResourceAccess.READ_ONLY,
    "campaigns": ResourceAccess.READ_ONLY,
    "funnels": ResourceAccess.READ_ONLY,
}


@dataclass
class BlueprintMetadata:
    name: str
    version: int = 1
    description: str = ""
    source_location_id: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class TagSpec:
    name: str


@dataclass
class CustomFieldSpec:
    name: str
    field_key: str
    data_type: str = "TEXT"
    placeholder: str | None = None
    position: int | None = None


@dataclass
class CustomValueSpec:
    name: str
    value: str


@dataclass
class PipelineStageSpec:
    name: str
    position: int | None = None


@dataclass
class PipelineSpec:
    name: str
    stages: list[PipelineStageSpec] = field(default_factory=list)


@dataclass
class CalendarSpec:
    name: str
    event_type: str | None = None


@dataclass
class WorkflowSpec:
    name: str
    status: str = "draft"


@dataclass
class FormSpec:
    name: str


@dataclass
class SurveySpec:
    name: str


@dataclass
class CampaignSpec:
    name: str
    status: str | None = None


@dataclass
class FunnelSpec:
    name: str
    steps: list[str] = field(default_factory=list)


@dataclass
class LocationBlueprint:
    metadata: BlueprintMetadata
    tags: list[TagSpec] = field(default_factory=list)
    custom_fields: list[CustomFieldSpec] = field(default_factory=list)
    custom_values: list[CustomValueSpec] = field(default_factory=list)
    pipelines: list[PipelineSpec] = field(default_factory=list)
    workflows: list[WorkflowSpec] = field(default_factory=list)
    calendars: list[CalendarSpec] = field(default_factory=list)
    forms: list[FormSpec] = field(default_factory=list)
    surveys: list[SurveySpec] = field(default_factory=list)
    campaigns: list[CampaignSpec] = field(default_factory=list)
    funnels: list[FunnelSpec] = field(default_factory=list)

    def resource_sections(self) -> dict[str, list]:
        """Return all resource sections as a dict."""
        return {
            "tags": self.tags,
            "custom_fields": self.custom_fields,
            "custom_values": self.custom_values,
            "pipelines": self.pipelines,
            "workflows": self.workflows,
            "calendars": self.calendars,
            "forms": self.forms,
            "surveys": self.surveys,
            "campaigns": self.campaigns,
            "funnels": self.funnels,
        }

    def provisionable_sections(self) -> dict[str, list]:
        """Return only FULL_CRUD sections."""
        return {
            k: v for k, v in self.resource_sections().items()
            if RESOURCE_ACCESS.get(k) == ResourceAccess.FULL_CRUD
        }

    def readonly_sections(self) -> dict[str, list]:
        """Return only READ_ONLY sections."""
        return {
            k: v for k, v in self.resource_sections().items()
            if RESOURCE_ACCESS.get(k) == ResourceAccess.READ_ONLY
        }
