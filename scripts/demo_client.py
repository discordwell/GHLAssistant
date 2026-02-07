#!/usr/bin/env python3
"""Demo of the GHL API client."""

import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from maxlevel.api import GHLClient, GHLConfig


async def main():
    # Load from latest session
    log_dir = Path(__file__).parent.parent / "data" / "network_logs"
    sessions = sorted(log_dir.glob("session_*.json"))
    if not sessions:
        print("No sessions found! Run 'maxlevel browser capture' first.")
        return

    session_file = sessions[-1]
    print(f"Loading from: {session_file.name}")

    # Create config
    config = GHLConfig.from_session_file(session_file)
    print(f"User ID: {config.user_id}")
    print(f"Company ID: {config.company_id}")

    async with GHLClient(config) as client:
        # Get user
        print("\n=== User Profile ===")
        user = await client.get_user()
        print(f"Name: {user.get('name')}")
        print(f"Email: {user.get('email')}")

        # Get company
        print("\n=== Company ===")
        company = await client.get_company()
        info = company.get("company", {})
        print(f"Name: {info.get('name')}")
        print(f"Plan: {info.get('plan')}")

        # Get locations
        print("\n=== Locations ===")
        locations = await client.search_locations()
        for loc in locations.get("locations", []):
            print(f"  - {loc.get('name')} ({loc.get('_id')})")
            
            # Set location for further queries
            config.location_id = loc.get("_id")

        if config.location_id:
            # Get workflows
            print("\n=== Workflows ===")
            workflows = await client.get_workflows()
            for wf in workflows.get("workflows", []):
                print(f"  - {wf.get('name')} [{wf.get('status')}]")

            # Get contacts
            print("\n=== Contacts ===")
            contacts = await client.get_contacts(limit=5)
            for c in contacts.get("contacts", []):
                print(f"  - {c.get('contactName')} ({c.get('email')})")

            # Get calendars
            print("\n=== Calendars ===")
            calendars = await client.get_calendars()
            for cal in calendars.get("calendars", []):
                print(f"  - {cal.get('name', 'Unnamed')} ({cal.get('eventType')})")

        print("\n✓ API client working!")


if __name__ == "__main__":
    asyncio.run(main())
