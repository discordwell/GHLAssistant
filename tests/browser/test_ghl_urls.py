from __future__ import annotations

from maxlevel.browser.ghl_urls import (
    contact_notes_url,
    contact_tasks_url,
    extract_location_contact_from_url,
)


def test_extract_location_contact_from_url_v2_route():
    url = "https://app.gohighlevel.com/v2/location/LOC123/contacts/detail/CON456?view=task"
    loc, cid = extract_location_contact_from_url(url)
    assert loc == "LOC123"
    assert cid == "CON456"


def test_extract_location_contact_from_url_location_route():
    url = "https://app.gohighlevel.com/location/LOC123/contacts/detail/CON456"
    loc, cid = extract_location_contact_from_url(url)
    assert loc == "LOC123"
    assert cid == "CON456"


def test_extract_location_contact_from_url_non_match():
    loc, cid = extract_location_contact_from_url("https://app.gohighlevel.com/")
    assert loc is None
    assert cid is None


def test_contact_notes_url_shape():
    assert (
        contact_notes_url(location_id="LOC123", contact_id="CON456")
        == "https://app.gohighlevel.com/location/LOC123/contacts/detail/CON456"
    )


def test_contact_tasks_url_shape():
    assert (
        contact_tasks_url(location_id="LOC123", contact_id="CON456")
        == "https://app.gohighlevel.com/v2/location/LOC123/contacts/detail/CON456?view=task"
    )
