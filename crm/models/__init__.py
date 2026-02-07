"""CRM models - re-exports all models and Base.metadata."""

from .base import Base, UUIDMixin, TimestampMixin, TenantMixin, GHLSyncMixin
from .location import Location
from .contact import Contact
from .tag import Tag, ContactTag
from .custom_field import CustomFieldDefinition, CustomFieldValue
from .custom_value import CustomValue
from .note import Note
from .task import Task
from .pipeline import Pipeline, PipelineStage
from .opportunity import Opportunity
from .activity import Activity

__all__ = [
    "Base",
    "UUIDMixin",
    "TimestampMixin",
    "TenantMixin",
    "GHLSyncMixin",
    "Location",
    "Contact",
    "ContactTag",
    "Tag",
    "CustomFieldDefinition",
    "CustomFieldValue",
    "CustomValue",
    "Note",
    "Task",
    "Pipeline",
    "PipelineStage",
    "Opportunity",
    "Activity",
]
