"""Bidirectional field mapping between GHL and local CRM."""

from __future__ import annotations

# GHL API field name -> local model attribute
CONTACT_FIELD_MAP: dict[str, str] = {
    "firstName": "first_name",
    "lastName": "last_name",
    "email": "email",
    "phone": "phone",
    "companyName": "company_name",
    "address1": "address1",
    "city": "city",
    "state": "state",
    "postalCode": "postal_code",
    "country": "country",
    "source": "source",
    "dnd": "dnd",
}

# Reverse mapping: local -> GHL
LOCAL_TO_GHL_CONTACT: dict[str, str] = {v: k for k, v in CONTACT_FIELD_MAP.items()}

OPPORTUNITY_FIELD_MAP: dict[str, str] = {
    "name": "name",
    "monetaryValue": "monetary_value",
    "status": "status",
    "source": "source",
}

LOCAL_TO_GHL_OPPORTUNITY: dict[str, str] = {v: k for k, v in OPPORTUNITY_FIELD_MAP.items()}


def ghl_contact_to_local(ghl_data: dict) -> dict:
    """Convert GHL contact dict to local field names."""
    result = {}
    for ghl_key, local_key in CONTACT_FIELD_MAP.items():
        if ghl_key in ghl_data and ghl_data[ghl_key] is not None:
            result[local_key] = ghl_data[ghl_key]
    return result


def local_contact_to_ghl(contact) -> dict:
    """Convert local Contact model to GHL API dict."""
    result = {}
    for local_key, ghl_key in LOCAL_TO_GHL_CONTACT.items():
        val = getattr(contact, local_key, None)
        if val is not None:
            result[ghl_key] = val
    return result


def ghl_opportunity_to_local(ghl_data: dict) -> dict:
    """Convert GHL opportunity dict to local field names."""
    result = {}
    for ghl_key, local_key in OPPORTUNITY_FIELD_MAP.items():
        if ghl_key in ghl_data and ghl_data[ghl_key] is not None:
            result[local_key] = ghl_data[ghl_key]
    return result


def local_opportunity_to_ghl(opp) -> dict:
    """Convert local Opportunity model to GHL API dict."""
    result = {}
    for local_key, ghl_key in LOCAL_TO_GHL_OPPORTUNITY.items():
        val = getattr(opp, local_key, None)
        if val is not None:
            result[ghl_key] = val
    return result
