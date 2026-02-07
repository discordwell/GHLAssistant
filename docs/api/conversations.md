# Conversations API

SMS, email, and messaging operations.

## Python API

```python
from maxlevel.api import GHLClient

async with GHLClient.from_session() as ghl:
    # List conversations
    convos = await ghl.conversations.list(limit=20)
    for c in convos["conversations"]:
        print(f"Contact: {c['contactId']} - Unread: {c['unreadCount']}")

    # Get unread only
    unread = await ghl.conversations.list(unread_only=True)

    # Get conversation messages
    messages = await ghl.conversations.messages(conversation_id)

    # Send SMS
    await ghl.conversations.send_sms(
        contact_id,
        message="Hello! This is a test message."
    )

    # Send Email
    await ghl.conversations.send_email(
        contact_id,
        subject="Hello from GHL",
        body="<p>This is the email body.</p>",
        from_name="Your Business",
        from_email="hello@yourdomain.com"
    )

    # Mark as read
    await ghl.conversations.mark_read(conversation_id)
```

## Message Types

- `SMS` - Text message
- `Email` - Email message
- `Call` - Phone call record
- `Facebook` - Facebook message
- `Instagram` - Instagram DM
- `WhatsApp` - WhatsApp message
