"""GHL API service - thin wrapper for accessing GHL client in CRM context."""

from __future__ import annotations

from typing import Any


class GHLNotLinkedError(Exception):
    """Raised when no GHL API token is configured."""


async def get_ghl_client():
    """Get an authenticated GHL client as async context manager.

    Usage:
        async with await get_ghl_client() as ghl:
            data = await ghl.contacts.list(location_id=loc_id)

    Raises:
        GHLNotLinkedError: If no valid token is available.
    """
    from maxlevel.api import GHLClient
    from maxlevel.auth.manager import TokenManager

    tm = TokenManager()
    if not tm.has_valid_token():
        raise GHLNotLinkedError("No GHL API token configured. Run 'maxlevel auth' to link your account.")

    return GHLClient.from_session()


async def fetch_conversations(
    ghl_location_id: str,
    limit: int = 20,
    unread_only: bool = False,
) -> dict[str, Any]:
    """Fetch conversations from GHL."""
    async with await get_ghl_client() as ghl:
        return await ghl.conversations.list(
            limit=limit, unread_only=unread_only, location_id=ghl_location_id,
        )


async def fetch_conversation_messages(conversation_id: str, limit: int = 50) -> dict[str, Any]:
    """Fetch messages for a conversation."""
    async with await get_ghl_client() as ghl:
        return await ghl.conversations.messages(conversation_id, limit=limit)


async def send_sms(contact_id: str, message: str, ghl_location_id: str) -> dict[str, Any]:
    """Send an SMS to a contact."""
    async with await get_ghl_client() as ghl:
        return await ghl.conversations.send_sms(contact_id, message, location_id=ghl_location_id)


async def send_email(
    contact_id: str, subject: str, body: str, ghl_location_id: str,
) -> dict[str, Any]:
    """Send an email to a contact."""
    async with await get_ghl_client() as ghl:
        return await ghl.conversations.send_email(
            contact_id, subject, body, location_id=ghl_location_id,
        )


async def mark_conversation_read(conversation_id: str) -> dict[str, Any]:
    """Mark a conversation as read."""
    async with await get_ghl_client() as ghl:
        return await ghl.conversations.mark_read(conversation_id)


async def fetch_calendars(ghl_location_id: str) -> dict[str, Any]:
    """Fetch calendars from GHL."""
    async with await get_ghl_client() as ghl:
        return await ghl.calendars.list(location_id=ghl_location_id)


async def fetch_calendar_slots(
    calendar_id: str, start_date: str, end_date: str, timezone: str = "America/New_York",
) -> dict[str, Any]:
    """Fetch available slots for a calendar."""
    async with await get_ghl_client() as ghl:
        return await ghl.calendars.get_slots(calendar_id, start_date, end_date, timezone=timezone)


async def book_appointment(
    calendar_id: str, contact_id: str, slot_time: str, ghl_location_id: str,
    title: str | None = None, notes: str | None = None,
) -> dict[str, Any]:
    """Book a calendar appointment."""
    async with await get_ghl_client() as ghl:
        return await ghl.calendars.book(
            calendar_id, contact_id, slot_time,
            title=title, notes=notes, location_id=ghl_location_id,
        )


async def cancel_appointment(appointment_id: str) -> dict[str, Any]:
    """Cancel a calendar appointment."""
    async with await get_ghl_client() as ghl:
        return await ghl.calendars.cancel(appointment_id)


async def fetch_forms(ghl_location_id: str) -> dict[str, Any]:
    """Fetch forms from GHL."""
    async with await get_ghl_client() as ghl:
        return await ghl.forms.list(location_id=ghl_location_id)


async def fetch_form_submissions(
    form_id: str, ghl_location_id: str, page: int = 1, limit: int = 50,
) -> dict[str, Any]:
    """Fetch submissions for a form."""
    async with await get_ghl_client() as ghl:
        return await ghl.forms.submissions(form_id, limit=limit, page=page, location_id=ghl_location_id)


async def fetch_surveys(ghl_location_id: str) -> dict[str, Any]:
    """Fetch surveys from GHL."""
    async with await get_ghl_client() as ghl:
        return await ghl.surveys.list(location_id=ghl_location_id)


async def fetch_survey_submissions(
    survey_id: str, ghl_location_id: str, page: int = 1, limit: int = 50,
) -> dict[str, Any]:
    """Fetch submissions for a survey."""
    async with await get_ghl_client() as ghl:
        return await ghl.surveys.submissions(survey_id, limit=limit, page=page, location_id=ghl_location_id)


async def fetch_campaigns(ghl_location_id: str) -> dict[str, Any]:
    """Fetch campaigns from GHL."""
    async with await get_ghl_client() as ghl:
        return await ghl.campaigns.list(location_id=ghl_location_id)


async def fetch_campaign(campaign_id: str) -> dict[str, Any]:
    """Fetch campaign details."""
    async with await get_ghl_client() as ghl:
        return await ghl.campaigns.get(campaign_id)


async def fetch_funnels(ghl_location_id: str) -> dict[str, Any]:
    """Fetch funnels from GHL."""
    async with await get_ghl_client() as ghl:
        return await ghl.funnels.list(location_id=ghl_location_id)


async def fetch_funnel_pages(funnel_id: str, ghl_location_id: str) -> dict[str, Any]:
    """Fetch pages for a funnel."""
    async with await get_ghl_client() as ghl:
        return await ghl.funnels.pages(funnel_id, location_id=ghl_location_id)
