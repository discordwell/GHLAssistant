"""Contacts API - Full CRUD operations for GHL contacts."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .client import GHLClient


class ContactsAPI:
    """Contacts API for GoHighLevel.

    Usage:
        async with GHLClient.from_session() as ghl:
            # List contacts
            contacts = await ghl.contacts.list(limit=50)

            # Create contact
            contact = await ghl.contacts.create(
                first_name="John",
                last_name="Doe",
                email="john@example.com",
                phone="+15551234567",
            )

            # Get single contact
            contact = await ghl.contacts.get("contact_id")

            # Update contact
            await ghl.contacts.update("contact_id", phone="+15559876543")

            # Delete contact
            await ghl.contacts.delete("contact_id")

            # Add tag
            await ghl.contacts.add_tag("contact_id", "hot-lead")

            # Add note
            await ghl.contacts.add_note("contact_id", "Called, left voicemail")
    """

    def __init__(self, client: "GHLClient"):
        self._client = client

    @property
    def _location_id(self) -> str:
        """Get location ID or raise error."""
        lid = self._client.config.location_id
        if not lid:
            raise ValueError("location_id required. Set via config or run 'maxlevel auth login'")
        return lid

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    async def list(
        self,
        limit: int = 20,
        offset: int = 0,
        query: str | None = None,
        location_id: str | None = None,
        start_after_id: str | None = None,
        start_after: int | None = None,
    ) -> dict[str, Any]:
        """List contacts for location.

        Args:
            limit: Max contacts to return (default 20, max 100)
            offset: Pagination offset (deprecated for this endpoint; ignored)
            query: Search query (searches name, email, phone)
            location_id: Override default location
            start_after_id: Cursor id for pagination (from response meta.startAfterId)
            start_after: Cursor timestamp for pagination (from response meta.startAfter)

        Returns:
            {"contacts": [...], "meta": {"total": N, ...}}
        """
        lid = location_id or self._location_id
        params: dict[str, Any] = {"locationId": lid, "limit": min(limit, 100)}
        if query:
            params["query"] = query
        if start_after_id:
            params["startAfterId"] = start_after_id
        if start_after is not None:
            params["startAfter"] = start_after
        return await self._client._get("/contacts/", **params)

    async def get(self, contact_id: str) -> dict[str, Any]:
        """Get a single contact by ID.

        Args:
            contact_id: The contact ID

        Returns:
            {"contact": {...}}
        """
        return await self._client._get(f"/contacts/{contact_id}")

    async def create(
        self,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        source: str = "api",
        tags: list[str] | None = None,
        custom_fields: dict[str, Any] | list[dict[str, Any]] | None = None,
        location_id: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Create a new contact.

        Args:
            first_name: First name
            last_name: Last name
            email: Email address
            phone: Phone number (E.164 format preferred, e.g., +15551234567)
            source: Lead source (default: "api")
            tags: List of tag names to add
            custom_fields: Custom field values
            location_id: Override default location
            **kwargs: Additional fields (companyName, address, city, state, etc.)

        Returns:
            {"contact": {...}} with created contact data
        """
        lid = location_id or self._location_id

        data = {"locationId": lid, "source": source}

        if first_name:
            data["firstName"] = first_name
        if last_name:
            data["lastName"] = last_name
        if email:
            data["email"] = email
        if phone:
            data["phone"] = phone
        if tags:
            data["tags"] = tags
        if custom_fields:
            data["customFields"] = custom_fields

        # Add any extra fields
        data.update(kwargs)

        return await self._client._post("/contacts/", data)

    async def update(
        self,
        contact_id: str,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        tags: list[str] | None = None,
        custom_fields: dict[str, Any] | list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Update an existing contact.

        Args:
            contact_id: The contact ID to update
            first_name: New first name
            last_name: New last name
            email: New email
            phone: New phone
            tags: Replace all tags with this list
            custom_fields: Update custom field values
            **kwargs: Additional fields to update

        Returns:
            {"contact": {...}} with updated contact data
        """
        data = {}

        if first_name is not None:
            data["firstName"] = first_name
        if last_name is not None:
            data["lastName"] = last_name
        if email is not None:
            data["email"] = email
        if phone is not None:
            data["phone"] = phone
        if tags is not None:
            data["tags"] = tags
        if custom_fields is not None:
            data["customFields"] = custom_fields

        data.update(kwargs)

        return await self._client._put(f"/contacts/{contact_id}", data)

    async def delete(self, contact_id: str) -> dict[str, Any]:
        """Delete a contact.

        Args:
            contact_id: The contact ID to delete

        Returns:
            {"succeeded": true} or error
        """
        return await self._client._delete(f"/contacts/{contact_id}")

    # =========================================================================
    # Tags
    # =========================================================================

    async def add_tag(self, contact_id: str, tag: str) -> dict[str, Any]:
        """Add a tag to a contact.

        Args:
            contact_id: The contact ID
            tag: Tag name to add

        Returns:
            Updated contact data
        """
        # Get current tags
        contact_data = await self.get(contact_id)
        current_tags = contact_data.get("contact", {}).get("tags", [])

        if tag not in current_tags:
            current_tags.append(tag)
            return await self.update(contact_id, tags=current_tags)

        return contact_data

    async def remove_tag(self, contact_id: str, tag: str) -> dict[str, Any]:
        """Remove a tag from a contact.

        Args:
            contact_id: The contact ID
            tag: Tag name to remove

        Returns:
            Updated contact data
        """
        contact_data = await self.get(contact_id)
        current_tags = contact_data.get("contact", {}).get("tags", [])

        if tag in current_tags:
            current_tags.remove(tag)
            return await self.update(contact_id, tags=current_tags)

        return contact_data

    # =========================================================================
    # Notes
    # =========================================================================

    async def add_note(
        self, contact_id: str, body: str, location_id: str | None = None
    ) -> dict[str, Any]:
        """Add a note to a contact.

        Args:
            contact_id: The contact ID
            body: Note content
            location_id: Override default location

        Returns:
            Created note data
        """
        lid = location_id or self._location_id
        return await self._client._post(
            "/notes/",
            {"contactId": contact_id, "body": body, "locationId": lid},
        )

    async def get_notes(
        self, contact_id: str, location_id: str | None = None
    ) -> dict[str, Any]:
        """Get notes for a contact.

        Args:
            contact_id: The contact ID
            location_id: Override default location

        Returns:
            {"notes": [...]}
        """
        lid = location_id or self._location_id
        return await self._client._get("/notes/", contactId=contact_id, locationId=lid)

    # =========================================================================
    # Tasks
    # =========================================================================

    async def add_task(
        self,
        contact_id: str,
        title: str,
        due_date: str | None = None,
        description: str | None = None,
        location_id: str | None = None,
    ) -> dict[str, Any]:
        """Add a task for a contact.

        Args:
            contact_id: The contact ID
            title: Task title
            due_date: Due date (ISO format)
            description: Task description
            location_id: Override default location

        Returns:
            Created task data
        """
        lid = location_id or self._location_id
        data = {
            "contactId": contact_id,
            "title": title,
            "locationId": lid,
        }
        if due_date:
            data["dueDate"] = due_date
        if description:
            data["description"] = description

        return await self._client._post("/tasks/", data)

    async def get_tasks(
        self, contact_id: str, location_id: str | None = None
    ) -> dict[str, Any]:
        """Get tasks for a contact.

        Args:
            contact_id: The contact ID
            location_id: Override default location

        Returns:
            {"tasks": [...]}
        """
        lid = location_id or self._location_id
        return await self._client._get("/tasks/", contactId=contact_id, locationId=lid)

    # =========================================================================
    # Workflows
    # =========================================================================

    async def add_to_workflow(
        self, contact_id: str, workflow_id: str, location_id: str | None = None
    ) -> dict[str, Any]:
        """Add contact to a workflow.

        Args:
            contact_id: The contact ID
            workflow_id: The workflow ID
            location_id: Override default location

        Returns:
            Result of adding contact to workflow
        """
        lid = location_id or self._location_id
        return await self._client._post(
            f"/workflows/{workflow_id}/contacts",
            {"contactId": contact_id, "locationId": lid},
        )

    async def remove_from_workflow(
        self, contact_id: str, workflow_id: str, location_id: str | None = None
    ) -> dict[str, Any]:
        """Remove contact from a workflow.

        Args:
            contact_id: The contact ID
            workflow_id: The workflow ID
            location_id: Override default location

        Returns:
            Result of removing contact from workflow
        """
        lid = location_id or self._location_id
        return await self._client._delete(
            f"/workflows/{workflow_id}/contacts/{contact_id}?locationId={lid}"
        )

    # =========================================================================
    # DND (Do Not Disturb)
    # =========================================================================

    async def set_dnd(
        self, contact_id: str, dnd: bool, channel: str = "all"
    ) -> dict[str, Any]:
        """Set Do Not Disturb status for a contact.

        Args:
            contact_id: The contact ID
            dnd: True to enable DND, False to disable
            channel: Channel to set DND for ("all", "sms", "email", "call")

        Returns:
            Updated contact data
        """
        if channel == "all":
            return await self.update(contact_id, dnd=dnd)
        else:
            dnd_settings = {channel: {"status": "active" if dnd else "inactive"}}
            return await self.update(contact_id, dndSettings=dnd_settings)

    # =========================================================================
    # Search
    # =========================================================================

    async def search(
        self,
        query: str,
        limit: int = 20,
        location_id: str | None = None,
    ) -> dict[str, Any]:
        """Search contacts by name, email, or phone.

        Args:
            query: Search string
            limit: Max results
            location_id: Override default location

        Returns:
            {"contacts": [...], "meta": {...}}
        """
        return await self.list(limit=limit, query=query, location_id=location_id)

    async def find_by_email(
        self, email: str, location_id: str | None = None
    ) -> dict[str, Any] | None:
        """Find a contact by email address.

        Args:
            email: Email to search for
            location_id: Override default location

        Returns:
            Contact data or None if not found
        """
        result = await self.search(email, limit=1, location_id=location_id)
        contacts = result.get("contacts", [])
        for contact in contacts:
            if contact.get("email", "").lower() == email.lower():
                return contact
        return None

    async def find_by_phone(
        self, phone: str, location_id: str | None = None
    ) -> dict[str, Any] | None:
        """Find a contact by phone number.

        Args:
            phone: Phone to search for
            location_id: Override default location

        Returns:
            Contact data or None if not found
        """
        result = await self.search(phone, limit=1, location_id=location_id)
        contacts = result.get("contacts", [])
        for contact in contacts:
            if contact.get("phone", "").replace("+", "").replace(" ", "") == phone.replace("+", "").replace(" ", ""):
                return contact
        return None
