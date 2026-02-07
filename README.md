# MaxLevel

GoHighLevel automation toolkit - Python API client and Claude Code integration.

## Features

- **Python API Client**: Full async client for GHL operations
- **Browser Auth Capture**: Session capture from GHL web app (since OAuth key creation is broken)
- **Claude Code Skill**: `/ghl` skill for AI-assisted automation
- **Modular Design**: Domain-specific APIs (contacts, workflows, calendars, etc.)

## Quick Start

### 1. Setup

```bash
# Clone and install
git clone https://github.com/discordwell/GHLAssistant.git
cd GHLAssistant

# Create virtual environment (Python 3.10+ required)
python3.12 -m venv venv
source venv/bin/activate
pip install -e .
```

### 2. Authenticate

Since GHL's OAuth key creation is broken, we capture auth from the browser:

```bash
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

This opens a browser - log into GHL, and the session will be captured automatically.

### 3. Use the API

```python
import asyncio
from maxlevel.api import GHLClient

async def main():
    async with GHLClient.from_session() as ghl:
        # List contacts
        contacts = await ghl.contacts.list(limit=10)
        print(f"Found {len(contacts['contacts'])} contacts")

        # Create a contact
        result = await ghl.contacts.create(
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            phone="+15551234567"
        )
        print(f"Created contact: {result['contact']['id']}")

asyncio.run(main())
```

## API Reference

### Contacts (`ghl.contacts`)

```python
# CRUD operations
await ghl.contacts.list(limit=20, query="search term")
await ghl.contacts.get(contact_id)
await ghl.contacts.create(first_name="John", email="john@example.com")
await ghl.contacts.update(contact_id, first_name="Jane")
await ghl.contacts.delete(contact_id)

# Tags & notes
await ghl.contacts.add_tag(contact_id, "vip")
await ghl.contacts.remove_tag(contact_id, "vip")
await ghl.contacts.add_note(contact_id, "Called, left voicemail")

# Workflows
await ghl.contacts.add_to_workflow(contact_id, workflow_id)

# Search
await ghl.contacts.find_by_email("john@example.com")
await ghl.contacts.find_by_phone("+15551234567")
```

### Workflows (`ghl.workflows`)

```python
await ghl.workflows.list()
await ghl.workflows.get(workflow_id)
await ghl.workflows.add_contact(workflow_id, contact_id)
await ghl.workflows.remove_contact(workflow_id, contact_id)
```

### Calendars (`ghl.calendars`)

```python
await ghl.calendars.list()
await ghl.calendars.get_slots(calendar_id, "2024-01-15", "2024-01-16")
await ghl.calendars.book(calendar_id, contact_id, slot_time)
await ghl.calendars.cancel(appointment_id)
await ghl.calendars.reschedule(appointment_id, new_time)
```

### Opportunities (`ghl.opportunities`)

```python
await ghl.opportunities.pipelines()
await ghl.opportunities.list(pipeline_id)
await ghl.opportunities.create(pipeline_id, stage_id, contact_id, name="Deal", value=5000)
await ghl.opportunities.move_stage(opp_id, new_stage_id)
await ghl.opportunities.mark_won(opp_id)
await ghl.opportunities.mark_lost(opp_id)
```

### Conversations (`ghl.conversations`)

```python
await ghl.conversations.list(unread_only=True)
await ghl.conversations.messages(conversation_id)
await ghl.conversations.send_sms(contact_id, "Hello!")  # Requires phone number in account
await ghl.conversations.send_email(contact_id, "Subject", "<p>Body</p>")
await ghl.conversations.mark_read(conversation_id)
```

### Forms (`ghl.forms`)

```python
await ghl.forms.list()
await ghl.forms.get(form_id)
await ghl.forms.submissions(form_id, limit=50)
```

## Claude Code Integration

Copy the skill to your Claude Code skills directory:

```bash
cp skills/ghl.md ~/.claude/skills/
```

Then use `/ghl` in Claude Code for GHL operations.

## Project Structure

```
GHLAssistant/
├── src/maxlevel/
│   ├── api/
│   │   ├── client.py        # Main GHLClient
│   │   ├── contacts.py      # Contacts API
│   │   ├── workflows.py     # Workflows API
│   │   ├── calendars.py     # Calendars API
│   │   ├── forms.py         # Forms API
│   │   ├── opportunities.py # Opportunities API
│   │   └── conversations.py # Messaging API
│   └── browser/
│       └── agent.py         # Browser auth capture
├── docs/
│   ├── ARCHITECTURE.md      # Design decisions
│   └── api/                 # API documentation
├── skills/
│   └── ghl.md               # Claude Code skill
└── data/
    └── network_logs/        # Captured sessions (gitignored)
```

## Technical Notes

- **Authentication**: Uses JWT tokens captured from browser. Tokens expire in ~1 hour.
- **Required Headers**: `version: 2021-07-28`, `channel: APP`, `source: WEB_USER`
- **Phone Format**: E.164 format (+15551234567)
- **SMS**: Requires a phone number purchased in GHL (~$1.15/month) and 10DLC registration

## License

MIT License
