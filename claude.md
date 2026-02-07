# MaxLevel Project Notes

## Default Ports
- **CRM Platform**: `8020` — `maxlevel crm serve`
- **Hiring Tool**: `8021` — `maxlevel hiring serve`
- **Workflow Builder**: `8022` — `maxlevel builder serve`

## Project Structure
```
src/maxlevel/           # Main CLI package (pip install -e ".[dev]")
  cli.py                # Typer CLI entry (name="maxlevel")
  api/                  # GHL API client (GHLClient + 15 domain APIs)
  auth/                 # TokenManager (OAuth + session)
  oauth/                # OAuth 2.0 flow
  blueprint/            # Location config as code
  browser/              # Browser automation (nodriver)
  hiring/               # Hiring funnel templates

crm/                    # CRM web app (FastAPI + HTMX + SQLAlchemy async)
hiring_tool/            # Hiring web app (FastAPI + HTMX + SQLModel)
workflows/              # Workflow Builder (FastAPI + HTMX + Drawflow + SQLAlchemy async)
```

## GHL API Quick Reference

All API methods use: `async with GHLClient.from_session() as ghl:`

### Contacts (`ghl.contacts`)
- `list(limit, query, location_id)` — List/search contacts
- `get(contact_id)` / `create(...)` / `update(contact_id, ...)` / `delete(contact_id)`
- `add_tag(contact_id, tag)` / `remove_tag(contact_id, tag)`
- `add_note(contact_id, body)` / `add_task(contact_id, title, due_date)`
- `add_to_workflow(contact_id, workflow_id)` / `send_sms/send_email` via conversations
- `find_by_email(email)` / `find_by_phone(phone)` — returns single contact or None

### Opportunities (`ghl.opportunities`)
- `pipelines(location_id)` — List all pipelines
- `list(pipeline_id, stage_id, contact_id, limit)` / `get(opp_id)` / `create(...)` / `update(...)`
- `move_stage(opp_id, stage_id)` / `mark_won(opp_id)` / `mark_lost(opp_id)`

### Conversations (`ghl.conversations`)
- `list(limit, unread_only)` / `messages(conversation_id, limit)`
- `send_sms(contact_id, message)` / `send_email(contact_id, subject, body)`
- `get_by_contact(contact_id)` / `mark_read(conversation_id)`

### Calendars (`ghl.calendars`)
- `list()` / `get(calendar_id)` / `get_slots(calendar_id, start_date, end_date)`
- `book(calendar_id, contact_id, slot_time)` / `cancel(appointment_id)`

### Tags (`ghl.tags`)
- `list()` / `create(name)` / `delete(tag_id)`

### Workflows (`ghl.workflows`)
- `list()` / `get(workflow_id)` / `add_contact(workflow_id, contact_id)`

### Custom Fields/Values (`ghl.custom_fields`, `ghl.custom_values`)
- `list()` / `create(name, ...)` / `delete(id)`

### Agency (`ghl.agency`) — requires company_id
- `list_locations()` / `create_location(name, ...)` / `delete_location(id)`
- `list_snapshots()` / `list_users()` / `invite_user(email, ...)`

### AI Agents (`ghl.conversation_ai`, `ghl.voice_ai`)
- `list_agents()` / `create_agent(name, prompt, ...)` / `update_agent(id, ...)`
- `list_actions(agent_id)` / `attach_action(agent_id, action_id)`

## Known GHL Platform Bugs

### Private Integrations - Create Button Not Working (2026-02-05)
Both sub-account and agency level Private Integration Create buttons don't work.
No API call is made when clicked. Affects all scope types.
**Workaround:** None known. Contact GHL support.
