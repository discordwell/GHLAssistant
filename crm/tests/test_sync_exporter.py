"""Test field mapper and export logic."""

from __future__ import annotations

import pytest

from crm.sync.field_mapper import (
    ghl_contact_to_local,
    local_contact_to_ghl,
    ghl_opportunity_to_local,
    CONTACT_FIELD_MAP,
)


def test_ghl_contact_to_local():
    ghl_data = {
        "firstName": "Alice",
        "lastName": "Smith",
        "email": "alice@test.com",
        "phone": "+1234567890",
        "companyName": "Acme",
        "source": "web",
        "dnd": True,
    }
    result = ghl_contact_to_local(ghl_data)
    assert result["first_name"] == "Alice"
    assert result["last_name"] == "Smith"
    assert result["email"] == "alice@test.com"
    assert result["company_name"] == "Acme"
    assert result["dnd"] is True


def test_ghl_contact_to_local_ignores_none():
    ghl_data = {"firstName": "Bob", "lastName": None, "email": "bob@test.com"}
    result = ghl_contact_to_local(ghl_data)
    assert "last_name" not in result
    assert result["first_name"] == "Bob"


def test_ghl_opportunity_to_local():
    ghl_data = {"name": "Big Deal", "monetaryValue": 5000.0, "status": "open"}
    result = ghl_opportunity_to_local(ghl_data)
    assert result["name"] == "Big Deal"
    assert result["monetary_value"] == 5000.0


def test_field_map_completeness():
    """Ensure all critical GHL fields are mapped."""
    expected = {"firstName", "lastName", "email", "phone", "companyName", "source", "dnd"}
    assert expected.issubset(set(CONTACT_FIELD_MAP.keys()))


class MockContact:
    first_name = "Test"
    last_name = "User"
    email = "test@example.com"
    phone = "+1111"
    company_name = "TestCo"
    address1 = None
    city = None
    state = None
    postal_code = None
    country = None
    source = "api"
    dnd = False


def test_local_contact_to_ghl():
    contact = MockContact()
    result = local_contact_to_ghl(contact)
    assert result["firstName"] == "Test"
    assert result["lastName"] == "User"
    assert result["email"] == "test@example.com"
    assert result["source"] == "api"
    assert "address1" not in result  # None values excluded
