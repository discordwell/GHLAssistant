# GHL Assistant

GoHighLevel automation toolkit - CLI tools, templates, and AI-powered wizards.

## Features

- **CLI Tool** (`ghl`): Command-line interface for common GHL operations
- **10DLC Wizard**: Interactive guide for SMS registration
- **Template Library**: Pre-built workflows and automations
- **Knowledge Base**: Embedded documentation for AI assistance

## Installation

```bash
# From source
pip install -e .

# Or with pipx (recommended)
pipx install .
```

## Quick Start

```bash
# Check auth status
ghl auth status

# Get 10DLC registration help
ghl 10dlc guide

# List available templates
ghl templates list
```

## Claude Code Integration

This toolkit is designed to work with Claude Code for AI-assisted GHL setup.

### Using with Claude Code

1. Add the official GHL MCP server:
```bash
claude mcp add ghl-official https://services.leadconnectorhq.com/mcp/
```

2. Use the knowledge base for context:
```
> Read knowledge/10dlc-complete-guide.md and help me register for 10DLC
```

3. Use custom skills:
```
> /ghl-10dlc
```

## Project Structure

```
GHLAssistant/
├── src/ghl_assistant/       # Python package
│   ├── cli.py               # CLI commands
│   └── api/                 # GHL API client
├── knowledge/               # Documentation for AI
│   ├── 10dlc-complete-guide.md
│   └── common-issues.md
├── prompts/                 # Claude Code skills
│   └── 10dlc-wizard.md
└── templates/               # Workflow templates
    └── workflows/
```

## Configuration

Create a `.env` file:

```env
GHL_API_KEY=your_api_key_here
GHL_LOCATION_ID=your_location_id
```

## CLI Commands

### Authentication
```bash
ghl auth login     # Start OAuth flow
ghl auth status    # Check connection
```

### 10DLC
```bash
ghl 10dlc status   # Check registration status
ghl 10dlc guide    # Interactive setup guide
```

### Templates
```bash
ghl templates list          # Browse available
ghl templates import <id>   # Import to account
```

## API Client Usage

```python
from ghl_assistant.api import GHLClient

async with GHLClient() as client:
    # List contacts
    contacts = await client.contacts.list()

    # Create contact
    contact = await client.contacts.create(
        name="John Doe",
        email="john@example.com"
    )

    # Add to workflow
    await client.contacts.add_to_workflow(
        contact_id=contact["id"],
        workflow_id="workflow_123"
    )
```

## License

MIT License - see LICENSE file.

## Contributing

PRs welcome! Please read CONTRIBUTING.md first.

## Roadmap

- [x] Phase 1: CLI + 10DLC wizard
- [ ] Phase 2: Workflow templates
- [ ] Phase 3: Dev tools (webhook tester, validator)
- [ ] Phase 4: Premium features
