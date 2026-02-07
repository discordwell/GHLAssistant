"""Calendars API - Calendar and booking operations for GHL."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .client import GHLClient


class CalendarsAPI:
    """Calendars API for GoHighLevel.

    Usage:
        async with GHLClient.from_session() as ghl:
            # List calendars
            calendars = await ghl.calendars.list()

            # Get available slots
            slots = await ghl.calendars.get_slots("calendar_id", "2024-01-15")

            # Book appointment
            await ghl.calendars.book("calendar_id", "contact_id", "2024-01-15T10:00:00Z")
    """

    def __init__(self, client: "GHLClient"):
        self._client = client

    @property
    def _location_id(self) -> str:
        lid = self._client.config.location_id
        if not lid:
            raise ValueError("location_id required")
        return lid

    async def list(self, location_id: str | None = None) -> dict[str, Any]:
        """List all calendars for location.

        Returns:
            {"calendars": [{"id": ..., "name": ..., "eventType": ...}, ...]}
        """
        lid = location_id or self._location_id
        return await self._client._get("/calendars/", locationId=lid)

    async def get(self, calendar_id: str) -> dict[str, Any]:
        """Get calendar details.

        Args:
            calendar_id: The calendar ID

        Returns:
            Calendar configuration and settings
        """
        return await self._client._get(f"/calendars/{calendar_id}")

    async def get_services(self, location_id: str | None = None) -> dict[str, Any]:
        """Get calendar services for location.

        Returns:
            {"services": [...]}
        """
        lid = location_id or self._location_id
        return await self._client._get("/calendars/services", locationId=lid)

    async def get_slots(
        self,
        calendar_id: str,
        start_date: str,
        end_date: str | None = None,
        timezone: str = "America/New_York",
    ) -> dict[str, Any]:
        """Get available slots for a calendar.

        Args:
            calendar_id: The calendar ID
            start_date: Start date (YYYY-MM-DD or ISO format)
            end_date: End date (defaults to start_date)
            timezone: Timezone for slots

        Returns:
            {"slots": {...}} with available time slots
        """
        params = {
            "calendarId": calendar_id,
            "startDate": start_date,
            "endDate": end_date or start_date,
            "timezone": timezone,
        }
        return await self._client._get("/calendars/slots", **params)

    async def get_appointments(
        self,
        calendar_id: str | None = None,
        contact_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        location_id: str | None = None,
    ) -> dict[str, Any]:
        """Get appointments.

        Args:
            calendar_id: Filter by calendar
            contact_id: Filter by contact
            start_date: Filter by start date
            end_date: Filter by end date
            location_id: Override default location

        Returns:
            {"appointments": [...]}
        """
        lid = location_id or self._location_id
        params = {"locationId": lid}
        if calendar_id:
            params["calendarId"] = calendar_id
        if contact_id:
            params["contactId"] = contact_id
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date

        return await self._client._get("/calendars/appointments", **params)

    async def book(
        self,
        calendar_id: str,
        contact_id: str,
        slot_time: str,
        title: str | None = None,
        notes: str | None = None,
        location_id: str | None = None,
    ) -> dict[str, Any]:
        """Book an appointment.

        Args:
            calendar_id: The calendar ID
            contact_id: The contact ID
            slot_time: Appointment time (ISO format)
            title: Appointment title
            notes: Appointment notes
            location_id: Override default location

        Returns:
            Created appointment data
        """
        lid = location_id or self._location_id
        data = {
            "calendarId": calendar_id,
            "contactId": contact_id,
            "startTime": slot_time,
            "locationId": lid,
        }
        if title:
            data["title"] = title
        if notes:
            data["notes"] = notes

        return await self._client._post("/calendars/appointments", data)

    async def cancel(self, appointment_id: str) -> dict[str, Any]:
        """Cancel an appointment.

        Args:
            appointment_id: The appointment ID

        Returns:
            Cancellation result
        """
        return await self._client._delete(f"/calendars/appointments/{appointment_id}")

    async def reschedule(
        self,
        appointment_id: str,
        new_slot_time: str,
    ) -> dict[str, Any]:
        """Reschedule an appointment.

        Args:
            appointment_id: The appointment ID
            new_slot_time: New appointment time (ISO format)

        Returns:
            Updated appointment data
        """
        return await self._client._put(
            f"/calendars/appointments/{appointment_id}",
            {"startTime": new_slot_time},
        )
