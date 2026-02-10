"""GHL API Client - Typed wrapper for GoHighLevel backend API.

Based on reverse-engineered endpoints from browser traffic capture.

Supports two authentication methods:
1. OAuth via TokenManager (recommended for production)
2. Session tokens from browser capture (for development)
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
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
    from .media_library import MediaLibraryAPI
    from .notes_service import NotesServiceAPI
    from .tasks_service import TasksServiceAPI
    from .conversation_ai import ConversationAIAPI
    from .voice_ai import VoiceAIAPI
    from .agency import AgencyAPI
    from ..auth.manager import TokenManager


def _session_logs_dir() -> Path | None:
    """Best-effort locate repo-local network logs (gitignored)."""
    # Running from repo: <root>/src/maxlevel/api/client.py
    try:
        root = Path(__file__).resolve().parents[3]
        candidate = root / "data" / "network_logs"
        if candidate.is_dir():
            return candidate
    except Exception:
        pass

    # Fallback: relative to CWD.
    try:
        candidate = Path.cwd() / "data" / "network_logs"
        if candidate.is_dir():
            return candidate
    except Exception:
        pass

    return None


def _scan_token_id_from_session_data(data: dict[str, Any]) -> str | None:
    auth_block = data.get("auth") or {}
    if isinstance(auth_block, dict):
        tok = auth_block.get("token_id")
        if isinstance(tok, str) and tok.strip():
            return tok.strip()

    # Best-effort: scan captured headers for `token-id`.
    def _scan(items: list[dict]) -> str | None:
        for item in items:
            if not isinstance(item, dict):
                continue
            headers = item.get("headers") or {}
            if not isinstance(headers, dict):
                continue
            for k, v in headers.items():
                if isinstance(k, str) and k.lower() == "token-id" and isinstance(v, str) and v.strip():
                    return v.strip()
        return None

    api_calls = data.get("api_calls", []) or []
    if isinstance(api_calls, list):
        tok = _scan([i for i in api_calls if isinstance(i, dict)])
        if tok:
            return tok

    network_log = data.get("network_log", []) or []
    if isinstance(network_log, list):
        tok = _scan([i for i in network_log if isinstance(i, dict)])
        if tok:
            return tok

    return None


def _scan_token_id_from_session_file(filepath: str | Path) -> str | None:
    try:
        raw = Path(filepath).read_text(encoding="utf-8")
    except Exception:
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return _scan_token_id_from_session_data(data)


@dataclass
class GHLConfig:
    """GHL API configuration."""

    token: str
    # Firebase ID token used by some services.* endpoints (e.g., media library upload).
    token_id: str | None = None
    user_id: str | None = None
    company_id: str | None = None
    location_id: str | None = None

    @classmethod
    def from_session_file(cls, filepath: str | Path | None = None) -> "GHLConfig":
        """Load config from a captured session file.

        If no filepath provided, uses the most recent session.

        Note: Consider using GHLClient.from_token_manager() instead,
        which supports both OAuth and session tokens with auto-refresh.
        """
        if filepath is None:
            # Find most recent session
            log_dir = Path(__file__).parent.parent.parent.parent / "data" / "network_logs"
            sessions = sorted(
                log_dir.glob("session_*.json"),
                key=lambda p: (p.stat().st_mtime if p.exists() else 0),
            )
            if not sessions:
                raise FileNotFoundError(
                    "No session files found. Run 'maxlevel auth quick' first."
                )
            filepath = sessions[-1]

        with open(filepath) as f:
            data = json.load(f)

        auth_block = data.get("auth") or {}
        cookie_auth_block = data.get("cookie_auth") or {}

        token = None
        if isinstance(auth_block, dict):
            token = auth_block.get("access_token")
        if not token and isinstance(cookie_auth_block, dict):
            token = cookie_auth_block.get("access_token")
        if not token:
            raise ValueError("No access token found in session file")

        token_id = _scan_token_id_from_session_data(data)

        # Extract IDs from auth blocks and API calls
        user_id = None
        company_id = None
        location_id = None

        if isinstance(auth_block, dict):
            user_id = auth_block.get("userId") if isinstance(auth_block.get("userId"), str) else None
            company_id = auth_block.get("companyId") if isinstance(auth_block.get("companyId"), str) else None
            location_id = (
                auth_block.get("locationId") if isinstance(auth_block.get("locationId"), str) else None
            )

        if isinstance(cookie_auth_block, dict):
            user_id = user_id or (
                cookie_auth_block.get("user_id") if isinstance(cookie_auth_block.get("user_id"), str) else None
            )
            company_id = company_id or (
                cookie_auth_block.get("company_id") if isinstance(cookie_auth_block.get("company_id"), str) else None
            )

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
            token_id=token_id,
            user_id=user_id,
            company_id=company_id,
            location_id=location_id,
        )

    @classmethod
    async def from_token_manager(cls, manager: "TokenManager" = None) -> "GHLConfig":
        """Load config from TokenManager (OAuth or session).

        This is the preferred method as it supports auto-refresh for OAuth tokens.

        Args:
            manager: TokenManager instance (uses default if not provided)

        Returns:
            GHLConfig with valid token
        """
        if manager is None:
            from ..auth.manager import TokenManager
            manager = TokenManager()

        token_info = await manager.get_token_info()

        return cls(
            token=token_info.token,
            user_id=token_info.user_id,
            company_id=token_info.company_id,
            location_id=token_info.location_id,
        )

    def to_dict(self) -> dict[str, Any]:
        """Export config as dictionary."""
        return {
            "token": self.token[:50] + "..." if self.token else None,
            "token_id": (self.token_id[:50] + "...") if self.token_id else None,
            "user_id": self.user_id,
            "company_id": self.company_id,
            "location_id": self.location_id,
        }


class GHLClient:
    """GoHighLevel API client with domain-specific sub-APIs.

    Usage with TokenManager (recommended):
        async with GHLClient.from_token_manager() as ghl:
            contacts = await ghl.contacts.list()

    Usage with session file (legacy):
        async with GHLClient.from_session() as ghl:
            contacts = await ghl.contacts.list()

    The TokenManager approach supports both OAuth tokens (with auto-refresh)
    and session tokens, choosing the best available option automatically.
    """

    BASE_URL = "https://backend.leadconnectorhq.com"

    REQUIRED_HEADERS = {
        "version": "2021-07-28",
        "channel": "APP",
        "source": "WEB_USER",
    }

    def __init__(self, config: GHLConfig, token_manager: "TokenManager" = None):
        """Initialize GHL client.

        Args:
            config: GHLConfig with token and IDs
            token_manager: Optional TokenManager for auto-refresh (OAuth)
        """
        self.config = config
        self._token_manager = token_manager
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
        self._media_library: MediaLibraryAPI | None = None
        self._notes_service: NotesServiceAPI | None = None
        self._tasks_service: TasksServiceAPI | None = None
        self._conversation_ai: ConversationAIAPI | None = None
        self._voice_ai: VoiceAIAPI | None = None
        self._agency: AgencyAPI | None = None

    def _best_effort_token_id(self) -> str | None:
        """Infer `token-id` (Firebase ID token) from env, stored session file, or recent logs."""
        override = os.environ.get("MAXLEVEL_TOKEN_ID")
        if isinstance(override, str) and override.strip():
            return override.strip()

        # TokenManager may remember the session file path.
        if self._token_manager:
            try:
                storage = self._token_manager.storage.load()
                session_file = storage.session.session_file if storage.session else None
                if isinstance(session_file, str) and session_file:
                    tok = _scan_token_id_from_session_file(session_file)
                    if tok:
                        return tok
            except Exception:
                pass

        log_dir = _session_logs_dir()
        if not log_dir:
            return None

        sessions = sorted(
            log_dir.glob("session_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:10]
        for path in sessions:
            tok = _scan_token_id_from_session_file(path)
            if tok:
                return tok

        return None

    @classmethod
    def from_session(cls, filepath: str | Path | None = None) -> "GHLClient":
        """Create client from available tokens (OAuth or session).

        This method first tries to use TokenManager (which supports OAuth
        with auto-refresh). If no tokens are available in TokenManager,
        it falls back to loading from session files.

        Args:
            filepath: Optional path to session file (bypasses TokenManager)

        Returns:
            GHLClient ready for API calls
        """
        # If explicit filepath provided, use session file directly
        if filepath:
            config = GHLConfig.from_session_file(filepath)
            return cls(config)

        # Try TokenManager first (sync check for any token)
        from ..auth.manager import TokenManager
        manager = TokenManager()

        if manager.has_valid_token():
            # Use a wrapper that will initialize with TokenManager
            # We can't do async in a classmethod, so we defer to __aenter__
            return cls._create_with_manager(manager)

        # Fall back to session file
        config = GHLConfig.from_session_file()
        return cls(config)

    @classmethod
    def _create_with_manager(cls, manager: "TokenManager") -> "GHLClient":
        """Create a client that will initialize with TokenManager in __aenter__."""
        # Create with placeholder config - will be replaced in __aenter__
        placeholder = GHLConfig(token="__pending__")
        client = cls(placeholder, token_manager=manager)
        client._needs_token_init = True
        return client

    @classmethod
    async def from_token_manager(cls, manager: "TokenManager" = None) -> "GHLClient":
        """Create client from TokenManager (recommended).

        Supports both OAuth (with auto-refresh) and session tokens.

        Args:
            manager: TokenManager instance (uses default if not provided)

        Returns:
            GHLClient ready for API calls
        """
        if manager is None:
            from ..auth.manager import TokenManager
            manager = TokenManager()

        config = await GHLConfig.from_token_manager(manager)
        return cls(config, token_manager=manager)

    async def _refresh_token_if_needed(self) -> None:
        """Refresh token if using TokenManager and token is expired."""
        if not self._token_manager:
            return

        # Get fresh token info (auto-refreshes OAuth if needed)
        token_info = await self._token_manager.get_token_info()

        # Update config and client headers if token changed
        if token_info.token != self.config.token:
            self.config.token = token_info.token
            if self._client:
                self._client.headers["Authorization"] = f"Bearer {token_info.token}"

    async def __aenter__(self) -> "GHLClient":
        # Handle deferred token initialization from from_session()
        if getattr(self, "_needs_token_init", False) and self._token_manager:
            token_info = await self._token_manager.get_token_info()
            self.config = GHLConfig(
                token=token_info.token,
                user_id=token_info.user_id,
                company_id=token_info.company_id,
                location_id=token_info.location_id,
            )
            self._needs_token_init = False

        # Best-effort: infer `token-id` for services.* endpoints (notes/tasks/media library).
        if not self.config.token_id:
            try:
                self.config.token_id = self._best_effort_token_id()
            except Exception:
                pass

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
        from .media_library import MediaLibraryAPI
        from .notes_service import NotesServiceAPI
        from .tasks_service import TasksServiceAPI
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
        self._media_library = MediaLibraryAPI(self)
        self._notes_service = NotesServiceAPI(self)
        self._tasks_service = TasksServiceAPI(self)
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
    def media_library(self) -> "MediaLibraryAPI":
        """Media Library API (best-effort; internal endpoints)."""
        if not self._media_library:
            raise RuntimeError("Client not initialized. Use 'async with' context.")
        return self._media_library

    @property
    def notes_service(self) -> "NotesServiceAPI":
        """Notes API via services.leadconnectorhq.com (requires token-id)."""
        if not self._notes_service:
            raise RuntimeError("Client not initialized. Use 'async with' context.")
        return self._notes_service

    @property
    def tasks_service(self) -> "TasksServiceAPI":
        """Tasks API via services.leadconnectorhq.com (requires token-id)."""
        if not self._tasks_service:
            raise RuntimeError("Client not initialized. Use 'async with' context.")
        return self._tasks_service

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
        await self._refresh_token_if_needed()
        resp = await self._client.get(endpoint, params=params)
        resp.raise_for_status()
        return resp.json()

    async def _post(self, endpoint: str, data: dict | None = None) -> dict[str, Any]:
        """Make POST request."""
        await self._refresh_token_if_needed()
        resp = await self._client.post(endpoint, json=data)
        resp.raise_for_status()
        return resp.json()

    async def _put(self, endpoint: str, data: dict | None = None) -> dict[str, Any]:
        """Make PUT request."""
        await self._refresh_token_if_needed()
        resp = await self._client.put(endpoint, json=data)
        resp.raise_for_status()
        return resp.json()

    async def _delete(self, endpoint: str) -> dict[str, Any]:
        """Make DELETE request."""
        await self._refresh_token_if_needed()
        resp = await self._client.delete(endpoint)
        resp.raise_for_status()
        return resp.json()

    async def _patch(self, endpoint: str, data: dict | None = None) -> dict[str, Any]:
        """Make PATCH request (used by Voice AI)."""
        await self._refresh_token_if_needed()
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
