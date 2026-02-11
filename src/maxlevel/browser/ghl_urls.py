"""Helpers for building/parsing common GoHighLevel app URLs.

These utilities are used by browser automation and capture tooling to
deep-link to specific screens (e.g., contact notes/tasks) with minimal
manual navigation.
"""

from __future__ import annotations

import re

from urllib.parse import urlencode


_CONTACT_DETAIL_RE = re.compile(
    r"/(?:v2/)?location/(?P<location_id>[^/]+)/contacts/detail/(?P<contact_id>[^/?#]+)",
    re.IGNORECASE,
)


def extract_location_contact_from_url(url: object) -> tuple[str | None, str | None]:
    """Extract (location_id, contact_id) from a GHL contact detail URL."""
    if not isinstance(url, str) or not url:
        return None, None
    match = _CONTACT_DETAIL_RE.search(url)
    if not match:
        return None, None
    return match.group("location_id"), match.group("contact_id")


def contact_notes_url(*, location_id: str, contact_id: str) -> str:
    """Best-effort deep link to a contact's Notes view."""
    # Observed pattern: /location/<location_id>/contacts/detail/<contact_id>
    return f"https://app.gohighlevel.com/location/{location_id}/contacts/detail/{contact_id}"


def contact_tasks_url(*, location_id: str, contact_id: str) -> str:
    """Best-effort deep link to a contact's Tasks view."""
    # Observed pattern: /v2/location/<location_id>/contacts/detail/<contact_id>?view=task
    qs = urlencode({"view": "task"})
    return f"https://app.gohighlevel.com/v2/location/{location_id}/contacts/detail/{contact_id}?{qs}"

