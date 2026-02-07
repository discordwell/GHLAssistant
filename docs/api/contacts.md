# Contacts API

Full CRUD operations for GHL contacts.

## CLI Commands

```bash
# List contacts
ghl contacts list [--limit 50] [--query "search term"]

# Get single contact
ghl contacts get <contact_id>

# Create contact
ghl contacts create \
  --first-name John \
  --last-name Doe \
  --email john@example.com \
  --phone "+15551234567"

# Update contact
ghl contacts update <contact_id> --phone "+15559876543"

# Delete contact
ghl contacts delete <contact_id>

# Tags
ghl contacts tag <contact_id> <tag_name>
ghl contacts untag <contact_id> <tag_name>

# Notes
ghl contacts add-note <contact_id> "Note content here"
ghl contacts notes <contact_id>

# Workflows
ghl contacts add-to-workflow <contact_id> <workflow_id>
```

## Python API

```python
from maxlevel.api import GHLClient

async with GHLClient.from_session() as ghl:
    # List contacts
    result = await ghl.contacts.list(limit=50)
    for contact in result["contacts"]:
        print(f"{contact['firstName']} {contact['lastName']}")

    # Create contact
    result = await ghl.contacts.create(
        first_name="John",
        last_name="Doe",
        email="john@example.com",
        phone="+15551234567",
        source="api",
        tags=["new-lead"],
    )
    contact_id = result["contact"]["id"]

    # Get contact
    contact = await ghl.contacts.get(contact_id)

    # Update contact
    await ghl.contacts.update(contact_id, phone="+15559876543")

    # Delete contact
    await ghl.contacts.delete(contact_id)

    # Tags
    await ghl.contacts.add_tag(contact_id, "hot-lead")
    await ghl.contacts.remove_tag(contact_id, "cold-lead")

    # Notes
    await ghl.contacts.add_note(contact_id, "Called, left voicemail")
    notes = await ghl.contacts.get_notes(contact_id)

    # Tasks
    await ghl.contacts.add_task(contact_id, "Follow up call", due_date="2024-01-15")
    tasks = await ghl.contacts.get_tasks(contact_id)

    # Workflows
    await ghl.contacts.add_to_workflow(contact_id, workflow_id)
    await ghl.contacts.remove_from_workflow(contact_id, workflow_id)

    # Search
    result = await ghl.contacts.search("john@example.com")
    contact = await ghl.contacts.find_by_email("john@example.com")
    contact = await ghl.contacts.find_by_phone("+15551234567")

    # DND (Do Not Disturb)
    await ghl.contacts.set_dnd(contact_id, True)  # Enable
    await ghl.contacts.set_dnd(contact_id, False)  # Disable
```

## Endpoints

### List Contacts
```
GET /contacts/?locationId={id}&limit=20&query={search}
```

**Response:**
```json
{
  "contacts": [
    {
      "id": "abc123",
      "locationId": "xyz789",
      "firstName": "John",
      "lastName": "Doe",
      "email": "john@example.com",
      "phone": "+15551234567",
      "tags": ["new-lead"],
      "source": "form",
      "dateAdded": "2024-01-01T00:00:00Z"
    }
  ],
  "meta": {
    "total": 100,
    "currentPage": 1
  }
}
```

### Create Contact
```
POST /contacts/
```

**Request:**
```json
{
  "locationId": "xyz789",
  "firstName": "John",
  "lastName": "Doe",
  "email": "john@example.com",
  "phone": "+15551234567",
  "source": "api",
  "tags": ["new-lead"],
  "customFields": {
    "field_key": "value"
  }
}
```

### Update Contact
```
PUT /contacts/{contact_id}
```

**Request:**
```json
{
  "firstName": "Jane",
  "phone": "+15559876543",
  "tags": ["hot-lead", "qualified"]
}
```

### Delete Contact
```
DELETE /contacts/{contact_id}
```

## Contact Fields

| Field | Type | Description |
|-------|------|-------------|
| id | string | Unique identifier |
| locationId | string | Parent location |
| firstName | string | First name |
| lastName | string | Last name |
| email | string | Email address |
| phone | string | Phone (E.164 format) |
| tags | string[] | Tag names |
| source | string | Lead source |
| dnd | boolean | Do Not Disturb |
| type | string | "lead" or "customer" |
| customFields | object | Custom field values |
| dateAdded | string | Creation timestamp |
| dateUpdated | string | Last update timestamp |
