"""GHL API Client - Typed wrapper for GoHighLevel backend API.

Based on reverse-engineered endpoints from browser traffic capture.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TYPE_CHECKING

import httpx

if TYPE_CHECKING:
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


@dataclass
class GHLConfig:
    """GHL API configuration."""

    token: str
    user_id: str | None = None
    company_id: str | None = None
    location_id: str | None = None

    @classmethod
    def from_session_file(cls, filepath: str | Path | None = None) -> "GHLConfig":
        """Load config from a captured session file.

        If no filepath provided, uses the most recent session.
        """
        if filepath is None:
            # Find most recent session
            log_dir = Path(__file__).parent.parent.parent.parent / "data" / "network_logs"
            sessions = sorted(log_dir.glob("session_*.json"))
            if not sessions:
                raise FileNotFoundError(
                    "No session files found. Run 'ghl auth login' first."
                )
            filepath = sessions[-1]

        with open(filepath) as f:
            data = json.load(f)

        token = data.get("auth", {}).get("access_token")
        if not token:
            raise ValueError("No access token found in session file")

        # Extract IDs from API calls
        user_id = None
        company_id = None
        location_id = None

        for call in data.get("api_calls", []):
            url = call.get("url", "")
            if "/users/" in url and not user_id:
                parts = url.split("/users/")
                if len(parts) > 1:
                    uid = parts[1].split("/")[0].split("?")[0]
                    if uid and uid != "identify":
                        user_id = uid
            if "companyId=" in url and not company_id:
                match = re.search(r"companyId=([a-zA-Z0-9]+)", url)
                if match:
                    company_id = match.group(1)
            if "locationId=" in url and not location_id:
                match = re.search(r"locationId=([a-zA-Z0-9]+)", url)
                if match and match.group(1) != "undefined":
                    location_id = match.group(1)

        return cls(
            token=token,
            user_id=user_id,
            company_id=company_id,
            location_id=location_id,
        )

    def to_dict(self) -> dict[str, Any]:
        """Export config as dictionary."""
        return {
            "token": self.token[:50] + "..." if self.token else None,
            "user_id": self.user_id,
            "company_id": self.company_id,
            "location_id": self.location_id,
        }


class GHLClient:
    """GoHighLevel API client with domain-specific sub-APIs.

    Usage:
        async with GHLClient.from_session() as ghl:
            # Domain-specific APIs
            contacts = await ghl.contacts.list()
            contact = await ghl.contacts.create(first_name="John", email="j@example.com")

            workflows = await ghl.workflows.list()
            calendars = await ghl.calendars.list()
    """

    BASE_URL = "https://backend.leadconnectorhq.com"

    REQUIRED_HEADERS = {
        "version": "2021-07-28",
        "channel": "APP",
        "source": "WEB_USER",
    }

    def __init__(self, config: GHLConfig):
        self.config = config
        self._client: httpx.AsyncClient | None = None

        # Domain APIs (initialized on enter)
        self._contacts: ContactsAPI | None = None
        self._workflows: WorkflowsAPI | None = None
        self._calendars: CalendarsAPI | None = None
        self._forms: FormsAPI | None = None
        self._opportunities: OpportunitiesAPI | None = None
        self._conversations: ConversationsAPI | None = None
        self._tags: TagsAPI | None = None
        self._custom_fields: CustomFieldsAPI | None = None
        self._custom_values: CustomValuesAPI | None = None
        self._campaigns: CampaignsAPI | None = None
        self._surveys: SurveysAPI | None = None
        self._funnels: FunnelsAPI | None = None
        self._conversation_ai: ConversationAIAPI | None = None
        self._voice_ai: VoiceAIAPI | None = None
        self._agency: AgencyAPI | None = None

    @classmethod
    def from_session(cls, filepath: str | Path | None = None) -> "GHLClient":
        """Create client from session file."""
        config = GHLConfig.from_session_file(filepath)
        return cls(config)

    async def __aenter__(self) -> "GHLClient":
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {self.config.token}",
                "Content-Type": "application/json",
                "Accept": "application/json, text/plain, */*",
                **self.REQUIRED_HEADERS,
            },
        )

        # Initialize domain APIs
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

        self._contacts = ContactsAPI(self)
        self._workflows = WorkflowsAPI(self)
        self._calendars = CalendarsAPI(self)
        self._forms = FormsAPI(self)
        self._opportunities = OpportunitiesAPI(self)
        self._conversations = ConversationsAPI(self)
        self._tags = TagsAPI(self)
        self._custom_fields = CustomFieldsAPI(self)
        self._custom_values = CustomValuesAPI(self)
        self._campaigns = CampaignsAPI(self)
        self._surveys = SurveysAPI(self)
        self._funnels = FunnelsAPI(self)
        self._conversation_ai = ConversationAIAPI(self)
        self._voice_ai = VoiceAIAPI(self)
        self._agency = AgencyAPI(self)

        # Auto-detect location if not set
        if not self.config.location_id and self.config.company_id:
            try:
                locations = await self.search_locations()
                if locations.get("locations"):
                    self.config.location_id = locations["locations"][0]["_id"]
            except Exception:
                pass  # Location detection is optional

        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    # Domain API properties
    @property
    def contacts(self) -> "ContactsAPI":
        """Contacts API."""
        if not self._contacts:
            raise RuntimeError("Client not initialized. Use 'async with' context.")
        return self._contacts

    @property
    def workflows(self) -> "WorkflowsAPI":
        """Workflows API."""
        if not self._workflows:
            raise RuntimeError("Client not initialized. Use 'async with' context.")
        return self._workflows

    @property
    def calendars(self) -> "CalendarsAPI":
        """Calendars API."""
        if not self._calendars:
            raise RuntimeError("Client not initialized. Use 'async with' context.")
        return self._calendars

    @property
    def forms(self) -> "FormsAPI":
        """Forms API."""
        if not self._forms:
            raise RuntimeError("Client not initialized. Use 'async with' context.")
        return self._forms

    @property
    def opportunities(self) -> "OpportunitiesAPI":
        """Opportunities/Pipelines API."""
        if not self._opportunities:
            raise RuntimeError("Client not initialized. Use 'async with' context.")
        return self._opportunities

    @property
    def conversations(self) -> "ConversationsAPI":
        """Conversations API."""
        if not self._conversations:
            raise RuntimeError("Client not initialized. Use 'async with' context.")
        return self._conversations

    @property
    def tags(self) -> "TagsAPI":
        """Tags API."""
        if not self._tags:
            raise RuntimeError("Client not initialized. Use 'async with' context.")
        return self._tags

    @property
    def custom_fields(self) -> "CustomFieldsAPI":
        """Custom Fields API."""
        if not self._custom_fields:
            raise RuntimeError("Client not initialized. Use 'async with' context.")
        return self._custom_fields

    @property
    def custom_values(self) -> "CustomValuesAPI":
        """Custom Values API."""
        if not self._custom_values:
            raise RuntimeError("Client not initialized. Use 'async with' context.")
        return self._custom_values

    @property
    def campaigns(self) -> "CampaignsAPI":
        """Campaigns API."""
        if not self._campaigns:
            raise RuntimeError("Client not initialized. Use 'async with' context.")
        return self._campaigns

    @property
    def surveys(self) -> "SurveysAPI":
        """Surveys API."""
        if not self._surveys:
            raise RuntimeError("Client not initialized. Use 'async with' context.")
        return self._surveys

    @property
    def funnels(self) -> "FunnelsAPI":
        """Funnels API."""
        if not self._funnels:
            raise RuntimeError("Client not initialized. Use 'async with' context.")
        return self._funnels

    @property
    def conversation_ai(self) -> "ConversationAIAPI":
        """Conversation AI API."""
        if not self._conversation_ai:
            raise RuntimeError("Client not initialized. Use 'async with' context.")
        return self._conversation_ai

    @property
    def voice_ai(self) -> "VoiceAIAPI":
        """Voice AI API."""
        if not self._voice_ai:
            raise RuntimeError("Client not initialized. Use 'async with' context.")
        return self._voice_ai

    @property
    def agency(self) -> "AgencyAPI":
        """Agency API for managing sub-accounts."""
        if not self._agency:
            raise RuntimeError("Client not initialized. Use 'async with' context.")
        return self._agency

    # HTTP methods
    async def _get(self, endpoint: str, **params) -> dict[str, Any]:
        """Make GET request."""
        resp = await self._client.get(endpoint, params=params)
        resp.raise_for_status()
        return resp.json()

    async def _post(self, endpoint: str, data: dict | None = None) -> dict[str, Any]:
        """Make POST request."""
        resp = await self._client.post(endpoint, json=data)
        resp.raise_for_status()
        return resp.json()

    async def _put(self, endpoint: str, data: dict | None = None) -> dict[str, Any]:
        """Make PUT request."""
        resp = await self._client.put(endpoint, json=data)
        resp.raise_for_status()
        return resp.json()

    async def _delete(self, endpoint: str) -> dict[str, Any]:
        """Make DELETE request."""
        resp = await self._client.delete(endpoint)
        resp.raise_for_status()
        return resp.json()

    async def _patch(self, endpoint: str, data: dict | None = None) -> dict[str, Any]:
        """Make PATCH request (used by Voice AI)."""
        resp = await self._client.patch(endpoint, json=data)
        resp.raise_for_status()
        return resp.json()

    # User & Company
    async def get_user(self, user_id: str | None = None) -> dict[str, Any]:
        """Get user profile."""
        uid = user_id or self.config.user_id
        if not uid:
            raise ValueError("user_id required")
        return await self._get(f"/users/{uid}")

    async def get_company(self, company_id: str | None = None) -> dict[str, Any]:
        """Get company info."""
        cid = company_id or self.config.company_id
        if not cid:
            raise ValueError("company_id required")
        return await self._get(f"/companies/{cid}")

    async def get_feature_flags(self, company_id: str | None = None) -> dict[str, Any]:
        """Get feature flags for company."""
        cid = company_id or self.config.company_id
        if not cid:
            raise ValueError("company_id required")
        return await self._get(f"/companies/{cid}/labs/featureFlags")

    # Locations
    async def search_locations(self, company_id: str | None = None) -> dict[str, Any]:
        """Search for locations under a company."""
        cid = company_id or self.config.company_id
        if not cid:
            raise ValueError("company_id required")
        return await self._get("/locations/search", companyId=cid)

    async def get_location(self, location_id: str | None = None) -> dict[str, Any]:
        """Get location details."""
        lid = location_id or self.config.location_id
        if not lid:
            raise ValueError("location_id required")
        return await self._get(f"/locations/{lid}")

    async def get_custom_values(self, location_id: str | None = None) -> dict[str, Any]:
        """Get custom values for location."""
        lid = location_id or self.config.location_id
        if not lid:
            raise ValueError("location_id required")
        return await self._get(f"/locations/{lid}/customValues")

    async def get_custom_fields(self, location_id: str | None = None) -> dict[str, Any]:
        """Get custom fields for location."""
        lid = location_id or self.config.location_id
        if not lid:
            raise ValueError("location_id required")
        return await self._get(f"/locations/{lid}/customFields")

    # Contacts
    async def get_contacts(
        self, location_id: str | None = None, limit: int = 20
    ) -> dict[str, Any]:
        """Get contacts for location."""
        lid = location_id or self.config.location_id
        if not lid:
            raise ValueError("location_id required")
        return await self._get("/contacts/", locationId=lid, limit=limit)

    async def get_contact(self, contact_id: str) -> dict[str, Any]:
        """Get single contact by ID."""
        return await self._get(f"/contacts/{contact_id}")

    # Conversations
    async def search_conversations(
        self, location_id: str | None = None
    ) -> dict[str, Any]:
        """Search conversations for location."""
        lid = location_id or self.config.location_id
        if not lid:
            raise ValueError("location_id required")
        return await self._get("/conversations/search", locationId=lid)

    # Calendars
    async def get_calendars(self, location_id: str | None = None) -> dict[str, Any]:
        """Get calendars for location."""
        lid = location_id or self.config.location_id
        if not lid:
            raise ValueError("location_id required")
        return await self._get("/calendars/", locationId=lid)

    async def get_calendar_services(
        self, location_id: str | None = None
    ) -> dict[str, Any]:
        """Get calendar services for location."""
        lid = location_id or self.config.location_id
        if not lid:
            raise ValueError("location_id required")
        return await self._get("/calendars/services", locationId=lid)

    # Pipelines
    async def get_pipelines(self, location_id: str | None = None) -> dict[str, Any]:
        """Get sales pipelines for location."""
        lid = location_id or self.config.location_id
        if not lid:
            raise ValueError("location_id required")
        return await self._get("/opportunities/pipelines", locationId=lid)

    # Workflows
    async def get_workflows(self, location_id: str | None = None) -> dict[str, Any]:
        """Get workflows for location."""
        lid = location_id or self.config.location_id
        if not lid:
            raise ValueError("location_id required")
        return await self._get("/workflows/", locationId=lid)

    # Forms & Surveys
    async def get_forms(self, location_id: str | None = None) -> dict[str, Any]:
        """Get forms for location."""
        lid = location_id or self.config.location_id
        if not lid:
            raise ValueError("location_id required")
        return await self._get("/forms/", locationId=lid)

    async def get_surveys(self, location_id: str | None = None) -> dict[str, Any]:
        """Get surveys for location."""
        lid = location_id or self.config.location_id
        if not lid:
            raise ValueError("location_id required")
        return await self._get("/surveys/", locationId=lid)

    # Campaigns & Funnels
    async def get_campaigns(self, location_id: str | None = None) -> dict[str, Any]:
        """Get campaigns for location."""
        lid = location_id or self.config.location_id
        if not lid:
            raise ValueError("location_id required")
        return await self._get("/campaigns/", locationId=lid)

    async def get_funnels(self, location_id: str | None = None) -> dict[str, Any]:
        """Get funnels for location."""
        lid = location_id or self.config.location_id
        if not lid:
            raise ValueError("location_id required")
        return await self._get("/funnels/", locationId=lid)

    # Billing
    async def get_billing_plan(self, company_id: str | None = None) -> dict[str, Any]:
        """Get billing plan for company."""
        cid = company_id or self.config.company_id
        if not cid:
            raise ValueError("company_id required")
        return await self._get(f"/internal-tools/billing/company/{cid}/plan")

    async def get_billing_info(self, company_id: str | None = None) -> dict[str, Any]:
        """Get billing info for company."""
        cid = company_id or self.config.company_id
        if not cid:
            raise ValueError("company_id required")
        return await self._get(f"/internal-tools/billing/company-info/{cid}")

    # OAuth/API Keys
    async def get_api_keys(
        self, company_id: str | None = None, limit: int = 10
    ) -> dict[str, Any]:
        """Get API keys for company."""
        cid = company_id or self.config.company_id
        if not cid:
            raise ValueError("company_id required")
        return await self._get(
            "/oauth/keys/", accountId=cid, type="Company", limit=limit, skip=0
        )

    # Notifications
    async def get_notifications(
        self, user_id: str | None = None, limit: int = 25
    ) -> dict[str, Any]:
        """Get notifications for user."""
        uid = user_id or self.config.user_id
        if not uid:
            raise ValueError("user_id required")
        return await self._get(
            f"/notifications/users/{uid}", limit=limit, skip=0, deleted=False
        )
