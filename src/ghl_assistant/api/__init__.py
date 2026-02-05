"""GHL API client module.

Usage:
    from ghl_assistant.api import GHLClient

    async with GHLClient.from_session() as ghl:
        # Contacts
        contacts = await ghl.contacts.list()
        contact = await ghl.contacts.create(first_name="John", email="j@example.com")

        # Workflows
        workflows = await ghl.workflows.list()

        # Calendars
        calendars = await ghl.calendars.list()

        # And more...
"""

from .client import GHLClient, GHLConfig
from .contacts import ContactsAPI
from .workflows import WorkflowsAPI
from .calendars import CalendarsAPI
from .forms import FormsAPI
from .opportunities import OpportunitiesAPI
from .conversations import ConversationsAPI
from .tags import TagsAPI
from .custom_fields import CustomFieldsAPI
from .custom_values import CustomValuesAPI
from .campaigns import CampaignsAPI
from .surveys import SurveysAPI
from .funnels import FunnelsAPI
from .conversation_ai import ConversationAIAPI
from .voice_ai import VoiceAIAPI
from .agency import AgencyAPI

__all__ = [
    "GHLClient",
    "GHLConfig",
    "ContactsAPI",
    "WorkflowsAPI",
    "CalendarsAPI",
    "FormsAPI",
    "OpportunitiesAPI",
    "ConversationsAPI",
    "TagsAPI",
    "CustomFieldsAPI",
    "CustomValuesAPI",
    "CampaignsAPI",
    "SurveysAPI",
    "FunnelsAPI",
    "ConversationAIAPI",
    "VoiceAIAPI",
    "AgencyAPI",
]
