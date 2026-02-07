---
name: ghl
description: GoHighLevel CRM automation - manage contacts, workflows, calendars, and more
---

# MaxLevel Skill

You are helping the user automate GoHighLevel (GHL) CRM operations. You have access to a Python API client and CLI tools.

## Setup

Before using GHL commands, ensure the user is authenticated:

```bash
# Check if session exists
ls data/network_logs/session_*.json 2>/dev/null | tail -1

# If no session, authenticate:
source venv/bin/activate
python -c "
import asyncio
from maxlevel.browser.agent import run_capture_session
asyncio.run(run_capture_session(
    url='https://app.gohighlevel.com/',
    profile='ghl_session',
    duration=30
))
"
```

## Python API Usage

Always use the async context manager:

```python
import asyncio
from maxlevel.api import GHLClient

async def main():
    async with GHLClient.from_session() as ghl:
        # Your code here
        pass

asyncio.run(main())
```

## Available APIs

### Contacts (`ghl.contacts`)
- `list(limit=20, query=None)` - List contacts
- `get(contact_id)` - Get single contact
- `create(first_name, last_name, email, phone, ...)` - Create contact
- `update(contact_id, ...)` - Update contact
- `delete(contact_id)` - Delete contact
- `add_tag(contact_id, tag)` - Add tag
- `remove_tag(contact_id, tag)` - Remove tag
- `add_note(contact_id, body)` - Add note
- `add_task(contact_id, title, due_date)` - Add task
- `add_to_workflow(contact_id, workflow_id)` - Add to workflow
- `find_by_email(email)` - Find by email
- `find_by_phone(phone)` - Find by phone

### Workflows (`ghl.workflows`)
- `list()` - List workflows
- `get(workflow_id)` - Get workflow details
- `add_contact(workflow_id, contact_id)` - Add contact to workflow
- `remove_contact(workflow_id, contact_id)` - Remove from workflow

### Calendars (`ghl.calendars`)
- `list()` - List calendars
- `get(calendar_id)` - Get calendar details
- `get_slots(calendar_id, start_date, end_date)` - Get available slots
- `book(calendar_id, contact_id, slot_time)` - Book appointment
- `cancel(appointment_id)` - Cancel appointment
- `reschedule(appointment_id, new_time)` - Reschedule

### Forms (`ghl.forms`)
- `list()` - List forms
- `get(form_id)` - Get form with fields
- `submissions(form_id, limit)` - Get submissions

### Opportunities (`ghl.opportunities`)
- `pipelines()` - List pipelines with stages
- `list(pipeline_id, stage_id)` - List opportunities
- `create(pipeline_id, stage_id, contact_id, name, value)` - Create
- `update(opp_id, ...)` - Update
- `move_stage(opp_id, stage_id)` - Move to stage
- `mark_won(opp_id)` / `mark_lost(opp_id)` - Close deal

### Conversations (`ghl.conversations`)
- `list(unread_only=False)` - List conversations
- `messages(conversation_id)` - Get messages
- `send_sms(contact_id, message)` - Send SMS
- `send_email(contact_id, subject, body)` - Send email
- `mark_read(conversation_id)` - Mark as read

## Common Tasks

### Create a lead and add to workflow
```python
async with GHLClient.from_session() as ghl:
    # Create contact
    result = await ghl.contacts.create(
        first_name="John",
        email="john@example.com",
        source="api"
    )
    contact_id = result["contact"]["id"]
    
    # Add to nurture workflow
    workflows = await ghl.workflows.list()
    nurture_wf = next(w for w in workflows["workflows"] if "nurture" in w["name"].lower())
    await ghl.workflows.add_contact(nurture_wf["id"], contact_id)
```

### Send follow-up message
```python
async with GHLClient.from_session() as ghl:
    contact = await ghl.contacts.find_by_email("john@example.com")
    if contact:
        await ghl.conversations.send_sms(
            contact["id"],
            "Hi! Just following up on our conversation."
        )
```

### Book appointment
```python
async with GHLClient.from_session() as ghl:
    calendars = await ghl.calendars.list()
    cal_id = calendars["calendars"][0]["id"]
    
    slots = await ghl.calendars.get_slots(cal_id, "2024-01-15")
    
    await ghl.calendars.book(
        cal_id,
        contact_id,
        slots["slots"]["2024-01-15"][0]["startTime"]
    )
```

## Error Handling

- **401 Unauthorized**: Token expired. Run auth again.
- **404 Not Found**: Resource doesn't exist.
- **422 Validation Error**: Check required fields.

## Notes

- Tokens expire in ~1 hour
- Location ID is auto-detected from session
- Phone numbers should be E.164 format (+15551234567)
- All times should be ISO 8601 format
