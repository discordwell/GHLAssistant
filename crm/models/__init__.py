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
from .conversation import Conversation, Message
from .calendar import Calendar, AvailabilityWindow, Appointment
from .form import Form, FormField, FormSubmission
from .survey import Survey, SurveyQuestion, SurveySubmission
from .campaign import Campaign, CampaignStep, CampaignEnrollment
from .funnel import Funnel, FunnelPage
from .ghl_raw import GHLRawEntity
from .asset import Asset, AssetRef, AssetJob, AssetRemoteMap
from .auth import AuthAccount, AuthInvite, AuthEvent

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
    "Conversation",
    "Message",
    "Calendar",
    "AvailabilityWindow",
    "Appointment",
    "Form",
    "FormField",
    "FormSubmission",
    "Survey",
    "SurveyQuestion",
    "SurveySubmission",
    "Campaign",
    "CampaignStep",
    "CampaignEnrollment",
    "Funnel",
    "FunnelPage",
    "GHLRawEntity",
    "Asset",
    "AssetRef",
    "AssetJob",
    "AssetRemoteMap",
    "AuthAccount",
    "AuthInvite",
    "AuthEvent",
]
