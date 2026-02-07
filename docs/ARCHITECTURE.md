# MaxLevel Architecture

## Vision

A comprehensive CLI toolkit that enables anyone with Claude Code to fully automate GoHighLevel operations from the command line. The system should be:

1. **Self-documenting** - Claude Code can read the docs and know what's possible
2. **Complete** - Cover all GHL operations (contacts, workflows, calendars, etc.)
3. **Simple** - `ghl contacts list` just works
4. **Extensible** - Easy to add new endpoints as GHL evolves

## Project Structure

```
GHLAssistant/
├── docs/
│   ├── api/                    # API endpoint documentation
│   │   ├── README.md           # API overview + auth
│   │   ├── contacts.md         # Contact CRUD operations
│   │   ├── workflows.md        # Workflow operations
│   │   ├── calendars.md        # Calendar operations
│   │   ├── opportunities.md    # Pipeline/opportunity ops
│   │   ├── conversations.md    # Messaging operations
│   │   ├── forms.md            # Form operations
│   │   └── ...
│   ├── guides/                 # How-to guides
│   │   ├── getting-started.md
│   │   ├── authentication.md
│   │   └── common-workflows.md
│   └── ARCHITECTURE.md         # This file
│
├── src/maxlevel/
│   ├── __init__.py
│   ├── cli.py                  # Main CLI entry point
│   │
│   ├── api/                    # API client layer
│   │   ├── __init__.py
│   │   ├── client.py           # Base client + auth
│   │   ├── contacts.py         # ContactsAPI class
│   │   ├── workflows.py        # WorkflowsAPI class
│   │   ├── calendars.py        # CalendarsAPI class
│   │   ├── opportunities.py    # OpportunitiesAPI class
│   │   ├── conversations.py    # ConversationsAPI class
│   │   ├── forms.py            # FormsAPI class
│   │   └── ...
│   │
│   ├── models/                 # Pydantic models
│   │   ├── __init__.py
│   │   ├── contact.py
│   │   ├── workflow.py
│   │   └── ...
│   │
│   ├── browser/                # Browser automation
│   │   ├── agent.py            # Browser control
│   │   └── network.py          # Traffic capture
│   │
│   └── commands/               # CLI command groups
│       ├── __init__.py
│       ├── contacts.py         # ghl contacts <cmd>
│       ├── workflows.py        # ghl workflows <cmd>
│       ├── calendars.py        # ghl calendars <cmd>
│       └── ...
│
├── skills/                     # Claude Code skills
│   └── ghl.md                  # Main GHL skill
│
├── scripts/                    # Utility scripts
│   ├── analyze_session.py
│   └── explore_api.py
│
└── data/                       # Runtime data (gitignored)
    ├── browser_profiles/
    ├── network_logs/
    └── sessions/
```

## Core Components

### 1. API Client (`src/maxlevel/api/`)

Modular async client with domain-specific classes:

```python
from maxlevel.api import GHLClient

async with GHLClient.from_session("session.json") as ghl:
    # Domain-specific APIs
    contacts = await ghl.contacts.list(limit=50)
    contact = await ghl.contacts.create(
        first_name="John",
        last_name="Doe",
        email="john@example.com"
    )
    await ghl.contacts.add_tag(contact.id, "new-lead")

    workflows = await ghl.workflows.list()
    await ghl.workflows.add_contact(workflow_id, contact.id)
```

### 2. CLI Commands (`src/maxlevel/commands/`)

Typer-based CLI mirroring the API structure:

```bash
# Contacts
ghl contacts list [--limit 50] [--query "email:*@gmail.com"]
ghl contacts get <contact_id>
ghl contacts create --first-name John --last-name Doe --email john@example.com
ghl contacts update <contact_id> --phone "+15551234567"
ghl contacts delete <contact_id>
ghl contacts tag <contact_id> <tag_name>
ghl contacts add-to-workflow <contact_id> <workflow_id>

# Workflows
ghl workflows list
ghl workflows get <workflow_id>
ghl workflows trigger <workflow_id> --contact <contact_id>

# Calendars
ghl calendars list
ghl calendars slots <calendar_id> --date 2024-01-15
ghl calendars book <calendar_id> --contact <contact_id> --slot "2024-01-15T10:00"

# Conversations
ghl conversations list [--unread]
ghl conversations send <contact_id> --message "Hello!"
ghl conversations history <contact_id>

# Forms
ghl forms list
ghl forms submissions <form_id>

# Browser/Auth
ghl auth login          # Opens browser, captures session
ghl auth status         # Shows current auth state
ghl auth refresh        # Refreshes token via browser
```

### 3. Documentation (`docs/api/`)

Each domain has a markdown file with:
- Endpoint reference
- Request/response examples
- Common use cases
- Error handling

Format optimized for Claude Code to parse and understand.

### 4. Claude Code Skill (`skills/ghl.md`)

A skill definition that:
- Describes all available GHL operations
- Shows example commands
- Provides troubleshooting guidance

## Authentication Flow

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  ghl auth login │────▶│  Browser Opens   │────▶│  User logs in   │
└─────────────────┘     │  (nodriver)      │     │  via Google     │
                        └──────────────────┘     └─────────────────┘
                                                          │
                                                          ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Session saved  │◀────│  Token captured  │◀────│  API traffic    │
│  to disk        │     │  from headers    │     │  intercepted    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐
│  ghl <command>  │  ← Uses saved session
└─────────────────┘
```

Session includes:
- JWT access token (expires in 1 hour)
- User ID, Company ID, Location ID
- Browser cookies for refresh

## Required Headers

All GHL API requests need:
```
Authorization: Bearer {token}
version: 2021-07-28
channel: APP
source: WEB_USER
```

## API Domains to Implement

| Domain | Priority | Status | Endpoints |
|--------|----------|--------|-----------|
| Contacts | P0 | 🟡 Partial | CRUD, tags, notes, tasks |
| Workflows | P0 | 🔴 TODO | List, trigger, add contact |
| Calendars | P1 | 🔴 TODO | List, slots, book, cancel |
| Opportunities | P1 | 🔴 TODO | CRUD, move stage |
| Conversations | P1 | 🔴 TODO | List, send SMS/email |
| Forms | P2 | 🟡 Partial | List, get, submissions |
| Funnels | P2 | 🔴 TODO | List, stats |
| Campaigns | P2 | 🔴 TODO | List, stats |
| Users | P2 | 🟡 Partial | Get profile |
| Locations | P2 | 🟡 Partial | List, get |
| Tags | P2 | 🔴 TODO | CRUD |
| Custom Fields | P2 | 🟡 Partial | List |
| Custom Values | P2 | 🟡 Partial | List |

## Next Steps

1. **Refactor API client** into modular domain classes
2. **Add Pydantic models** for type safety
3. **Build CLI commands** for each domain
4. **Write API docs** for each endpoint
5. **Create Claude Code skill** for GHL operations
6. **Add session management** with auto-refresh
