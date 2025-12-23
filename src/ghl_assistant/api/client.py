"""GHL API Client - Wrapper for GoHighLevel API."""

import os
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

GHL_API_BASE = "https://services.leadconnectorhq.com"


class GHLError(Exception):
    """Base exception for GHL API errors."""

    def __init__(self, message: str, status_code: int | None = None, response: dict | None = None):
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(self.message)


class GHLAuthError(GHLError):
    """Authentication error."""

    pass


class GHLRateLimitError(GHLError):
    """Rate limit exceeded."""

    pass


class GHLClient:
    """GoHighLevel API client with ergonomic interface.

    Usage:
        client = GHLClient()
        contacts = await client.contacts.list()
        contact = await client.contacts.create(name="John", email="john@example.com")
    """

    def __init__(
        self,
        api_key: str | None = None,
        location_id: str | None = None,
        base_url: str = GHL_API_BASE,
    ):
        self.api_key = api_key or os.getenv("GHL_API_KEY")
        self.location_id = location_id or os.getenv("GHL_LOCATION_ID")
        self.base_url = base_url

        if not self.api_key:
            raise GHLAuthError("GHL_API_KEY not set. Run 'ghl auth login' or set in .env")

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Version": "2021-07-28",
            },
            timeout=30.0,
        )

        # Sub-clients for different resources
        self.contacts = ContactsClient(self)
        self.conversations = ConversationsClient(self)
        self.opportunities = OpportunitiesClient(self)
        self.calendars = CalendarsClient(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        json: dict | None = None,
    ) -> dict[str, Any]:
        """Make an API request with error handling."""
        try:
            response = await self._client.request(
                method=method,
                url=path,
                params=params,
                json=json,
            )

            if response.status_code == 401:
                raise GHLAuthError("Invalid API key or token expired", 401)

            if response.status_code == 429:
                raise GHLRateLimitError(
                    "Rate limit exceeded. Wait and retry.",
                    429,
                    response.json() if response.content else None,
                )

            response.raise_for_status()
            return response.json() if response.content else {}

        except httpx.HTTPStatusError as e:
            raise GHLError(
                f"API error: {e.response.status_code}",
                e.response.status_code,
                e.response.json() if e.response.content else None,
            )


class ContactsClient:
    """Contacts API operations."""

    def __init__(self, client: GHLClient):
        self._client = client

    async def list(self, limit: int = 20, start_after: str | None = None) -> dict:
        """List contacts in the location."""
        params = {"locationId": self._client.location_id, "limit": limit}
        if start_after:
            params["startAfter"] = start_after
        return await self._client._request("GET", "/contacts/", params=params)

    async def get(self, contact_id: str) -> dict:
        """Get a contact by ID."""
        return await self._client._request("GET", f"/contacts/{contact_id}")

    async def create(
        self,
        email: str | None = None,
        phone: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        name: str | None = None,
        **kwargs,
    ) -> dict:
        """Create a new contact."""
        data = {"locationId": self._client.location_id}
        if email:
            data["email"] = email
        if phone:
            data["phone"] = phone
        if first_name:
            data["firstName"] = first_name
        if last_name:
            data["lastName"] = last_name
        if name:
            data["name"] = name
        data.update(kwargs)
        return await self._client._request("POST", "/contacts/", json=data)

    async def update(self, contact_id: str, **kwargs) -> dict:
        """Update a contact."""
        return await self._client._request("PUT", f"/contacts/{contact_id}", json=kwargs)

    async def delete(self, contact_id: str) -> dict:
        """Delete a contact."""
        return await self._client._request("DELETE", f"/contacts/{contact_id}")

    async def add_to_workflow(self, contact_id: str, workflow_id: str) -> dict:
        """Add contact to a workflow."""
        return await self._client._request(
            "POST",
            f"/contacts/{contact_id}/workflow/{workflow_id}",
        )


class ConversationsClient:
    """Conversations API operations."""

    def __init__(self, client: GHLClient):
        self._client = client

    async def list(self, contact_id: str | None = None, limit: int = 20) -> dict:
        """List conversations."""
        params = {"locationId": self._client.location_id, "limit": limit}
        if contact_id:
            params["contactId"] = contact_id
        return await self._client._request("GET", "/conversations/", params=params)

    async def send_message(
        self,
        conversation_id: str,
        message: str,
        message_type: str = "SMS",
    ) -> dict:
        """Send a message in a conversation."""
        return await self._client._request(
            "POST",
            f"/conversations/{conversation_id}/messages",
            json={
                "type": message_type,
                "message": message,
            },
        )


class OpportunitiesClient:
    """Opportunities/Pipeline API operations."""

    def __init__(self, client: GHLClient):
        self._client = client

    async def list(self, pipeline_id: str | None = None, limit: int = 20) -> dict:
        """List opportunities."""
        params = {"locationId": self._client.location_id, "limit": limit}
        if pipeline_id:
            params["pipelineId"] = pipeline_id
        return await self._client._request("GET", "/opportunities/", params=params)

    async def create(
        self,
        pipeline_id: str,
        stage_id: str,
        contact_id: str,
        name: str,
        **kwargs,
    ) -> dict:
        """Create a new opportunity."""
        data = {
            "locationId": self._client.location_id,
            "pipelineId": pipeline_id,
            "pipelineStageId": stage_id,
            "contactId": contact_id,
            "name": name,
        }
        data.update(kwargs)
        return await self._client._request("POST", "/opportunities/", json=data)


class CalendarsClient:
    """Calendars API operations."""

    def __init__(self, client: GHLClient):
        self._client = client

    async def list(self) -> dict:
        """List calendars."""
        return await self._client._request(
            "GET",
            "/calendars/",
            params={"locationId": self._client.location_id},
        )

    async def get_slots(
        self,
        calendar_id: str,
        start_date: str,
        end_date: str,
    ) -> dict:
        """Get available slots for a calendar."""
        return await self._client._request(
            "GET",
            f"/calendars/{calendar_id}/free-slots",
            params={
                "startDate": start_date,
                "endDate": end_date,
            },
        )
