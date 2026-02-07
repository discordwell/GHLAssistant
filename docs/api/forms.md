# Forms API

Form and submission operations.

## Python API

```python
from maxlevel.api import GHLClient

async with GHLClient.from_session() as ghl:
    # List forms
    result = await ghl.forms.list()
    for form in result["forms"]:
        print(f"{form['name']} - {form['_id']}")

    # Get form details (includes fields)
    form = await ghl.forms.get(form_id)
    for field in form["form"]["formData"]["form"]["fields"]:
        print(f"  {field['label']} ({field['type']})")

    # Get submissions
    submissions = await ghl.forms.submissions(form_id, limit=50)
    print(f"Total submissions: {submissions['meta']['total']}")

    # Get all submissions (all forms)
    all_subs = await ghl.forms.all_submissions(limit=100)
```

## Form Fields

Common field types:
- `text` - Text input
- `email` - Email input
- `phone` - Phone input
- `textarea` - Multi-line text
- `select` - Dropdown
- `checkbox` - Checkbox
- `radio` - Radio buttons
- `date` - Date picker
- `submit` - Submit button
