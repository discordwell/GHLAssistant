"""Conversations API - Messaging operations for GHL."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .client import GHLClient


class ConversationsAPI:
    """Conversations API for GoHighLevel.

    Usage:
        async with GHLClient.from_session() as ghl:
            # List conversations
            conversations = await ghl.conversations.list()

            # Get conversation history
            messages = await ghl.conversations.messages("conversation_id")

            # Send SMS
            await ghl.conversations.send_sms("contact_id", "Hello!")

            # Send email
            await ghl.conversations.send_email(
                "contact_id",
                subject="Hello",
                body="<p>Hi there!</p>",
            )
    """

    def __init__(self, client: "GHLClient"):
        self._client = client

    @property
    def _location_id(self) -> str:
        lid = self._client.config.location_id
        if not lid:
            raise ValueError("location_id required")
        return lid

    async def list(
        self,
        limit: int = 20,
        unread_only: bool = False,
        location_id: str | None = None,
    ) -> dict[str, Any]:
        """List conversations.

        Args:
            limit: Max results
            unread_only: Only return unread conversations
            location_id: Override default location

        Returns:
            {"conversations": [...], "total": N}
        """
        lid = location_id or self._location_id
        params = {"locationId": lid, "limit": limit}
        if unread_only:
            params["status"] = "unread"

        return await self._client._get("/conversations/search", **params)

    async def get(self, conversation_id: str) -> dict[str, Any]:
        """Get conversation details.

        Args:
            conversation_id: The conversation ID

        Returns:
            Conversation data
        """
        return await self._client._get(f"/conversations/{conversation_id}")

    async def messages(
        self,
        conversation_id: str,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Get messages in a conversation.

        Args:
            conversation_id: The conversation ID
            limit: Max messages to return

        Returns:
            {"messages": [...]}
        """
        return await self._client._get(
            f"/conversations/{conversation_id}/messages",
            limit=limit,
        )

    async def get_by_contact(
        self,
        contact_id: str,
        location_id: str | None = None,
    ) -> dict[str, Any]:
        """Get conversation for a specific contact.

        Args:
            contact_id: The contact ID
            location_id: Override default location

        Returns:
            Conversation data or creates new one
        """
        lid = location_id or self._location_id
        return await self._client._get(
            "/conversations/search",
            locationId=lid,
            contactId=contact_id,
        )

    async def send_sms(
        self,
        contact_id: str,
        message: str,
        location_id: str | None = None,
    ) -> dict[str, Any]:
        """Send an SMS message to a contact.

        Args:
            contact_id: The contact ID
            message: SMS message text
            location_id: Override default location

        Returns:
            Sent message data
        """
        lid = location_id or self._location_id
        return await self._client._post(
            "/conversations/messages",
            {
                "contactId": contact_id,
                "locationId": lid,
                "type": "SMS",
                "message": message,
            },
        )

    async def send_email(
        self,
        contact_id: str,
        subject: str,
        body: str,
        from_name: str | None = None,
        from_email: str | None = None,
        location_id: str | None = None,
    ) -> dict[str, Any]:
        """Send an email to a contact.

        Args:
            contact_id: The contact ID
            subject: Email subject
            body: Email body (HTML supported)
            from_name: Sender name
            from_email: Sender email
            location_id: Override default location

        Returns:
            Sent message data
        """
        lid = location_id or self._location_id
        data = {
            "contactId": contact_id,
            "locationId": lid,
            "type": "Email",
            "subject": subject,
            "html": body,
        }
        if from_name:
            data["fromName"] = from_name
        if from_email:
            data["fromEmail"] = from_email

        return await self._client._post("/conversations/messages", data)

    async def mark_read(self, conversation_id: str) -> dict[str, Any]:
        """Mark a conversation as read.

        Args:
            conversation_id: The conversation ID

        Returns:
            Updated conversation
        """
        return await self._client._put(
            f"/conversations/{conversation_id}",
            {"unreadCount": 0},
        )

    async def add_inbound_message(
        self,
        conversation_id: str,
        message: str,
        message_type: str = "SMS",
    ) -> dict[str, Any]:
        """Add an inbound message to conversation (for testing/simulation).

        Args:
            conversation_id: The conversation ID
            message: Message content
            message_type: Type of message (SMS, Email, etc.)

        Returns:
            Created message
        """
        return await self._client._post(
            f"/conversations/{conversation_id}/messages/inbound",
            {"type": message_type, "message": message},
        )
