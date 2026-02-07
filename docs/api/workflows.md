# Workflows API

Automation workflow operations.

## CLI Commands

```bash
# List workflows
ghl workflows list

# Get workflow details
ghl workflows get <workflow_id>

# Add contact to workflow
ghl workflows add-contact <workflow_id> <contact_id>

# Remove contact from workflow
ghl workflows remove-contact <workflow_id> <contact_id>
```

## Python API

```python
from maxlevel.api import GHLClient

async with GHLClient.from_session() as ghl:
    # List workflows
    result = await ghl.workflows.list()
    for wf in result["workflows"]:
        print(f"{wf['name']} - {wf['status']}")

    # Get workflow details
    workflow = await ghl.workflows.get(workflow_id)

    # Add contact to workflow
    await ghl.workflows.add_contact(workflow_id, contact_id)

    # Remove contact from workflow
    await ghl.workflows.remove_contact(workflow_id, contact_id)
```

## Endpoints

### List Workflows
```
GET /workflows/?locationId={id}
```

**Response:**
```json
{
  "workflows": [
    {
      "id": "abc123",
      "name": "New Lead Nurture",
      "status": "published",  // "draft" or "published"
      "locationId": "xyz789",
      "createdAt": "2024-01-01T00:00:00Z",
      "updatedAt": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### Add Contact to Workflow
```
POST /workflows/{workflow_id}/contacts
```

**Request:**
```json
{
  "contactId": "contact123",
  "locationId": "xyz789"
}
```

## Workflow Status

- `draft` - Not active, won't trigger
- `published` - Active and will trigger

## Notes

- Only published workflows will execute when contacts are added
- Contacts can be in multiple workflows simultaneously
- Removing a contact stops the workflow for that contact
