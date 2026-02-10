"""GHL API client module.

Usage with TokenManager (recommended - supports OAuth with auto-refresh):
    from maxlevel.api import GHLClient

    async with GHLClient.from_session() as ghl:
        # Automatically uses OAuth if available, falls back to session token
        contacts = await ghl.contacts.list()
        contact = await ghl.contacts.create(first_name="John", email="j@example.com")

        # Workflows
        workflows = await ghl.workflows.list()

        # Calendars
        calendars = await ghl.calendars.list()

        # And more...

For direct TokenManager access:
    from maxlevel.auth import TokenManager

    manager = TokenManager()
    token = await manager.get_token()  # Gets valid token, auto-refreshes OAuth
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
from .media_library import MediaLibraryAPI
from .notes_service import NotesServiceAPI
from .tasks_service import TasksServiceAPI
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
    "MediaLibraryAPI",
    "NotesServiceAPI",
    "TasksServiceAPI",
    "ConversationAIAPI",
    "VoiceAIAPI",
    "AgencyAPI",
]
