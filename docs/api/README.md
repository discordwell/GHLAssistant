# GHL API Reference

Complete API documentation for GoHighLevel automation via the `ghl` CLI and Python client.

## Quick Start

```bash
# Authenticate (opens browser, captures session)
ghl auth login

# List contacts
ghl contacts list

# Create a contact
ghl contacts create --first-name John --last-name Doe --email john@example.com

# List workflows
ghl workflows list
```

## Python Client

```python
from maxlevel.api import GHLClient

async with GHLClient.from_session() as ghl:
    # All APIs available via properties
    contacts = await ghl.contacts.list()
    workflows = await ghl.workflows.list()
    calendars = await ghl.calendars.list()
```

## Authentication

GHL uses JWT tokens with these required headers:

```
Authorization: Bearer {token}
version: 2021-07-28
channel: APP
source: WEB_USER
```

Tokens expire in ~1 hour. Use `ghl auth login` to refresh.

## API Domains

| Domain | Description | Doc |
|--------|-------------|-----|
| [Contacts](./contacts.md) | Contact CRUD, tags, notes, tasks | Full |
| [Workflows](./workflows.md) | Automation workflows | Full |
| [Calendars](./calendars.md) | Calendars, appointments, booking | Full |
| [Forms](./forms.md) | Forms and submissions | Full |
| [Opportunities](./opportunities.md) | Pipelines and deals | Full |
| [Conversations](./conversations.md) | SMS, email, messaging | Full |

## Account Hierarchy

```
Company (Agency)
├── User (your account)
└── Location (sub-account) ← Most APIs operate here
    ├── Contacts
    ├── Workflows
    ├── Calendars
    ├── Pipelines
    └── ...
```

## Error Handling

Common HTTP status codes:
- `200` - Success
- `201` - Created
- `400` - Bad request (check params)
- `401` - Token expired (run `ghl auth login`)
- `404` - Resource not found
- `422` - Validation error (check required fields)

## Rate Limits

GHL rate limits are not publicly documented. The client includes retry logic for transient failures.
