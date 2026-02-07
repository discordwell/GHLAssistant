"""Tests for GHL sync engine."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlmodel import Session

from hiring_tool.models import Candidate, CandidateActivity
from hiring_tool.services.sync_engine import (
    _candidate_to_ghl_contact,
    _ghl_contact_to_candidate_fields,
    push_all_to_ghl,
    pull_from_ghl,
)


def test_candidate_to_ghl_contact_basic():
    c = Candidate(
        first_name="Jane",
        last_name="Doe",
        email="jane@test.com",
        phone="+1555",
    )
    result = _candidate_to_ghl_contact(c)
    assert result["firstName"] == "Jane"
    assert result["lastName"] == "Doe"
    assert result["email"] == "jane@test.com"
    assert result["phone"] == "+1555"


def test_candidate_to_ghl_contact_with_custom_fields():
    c = Candidate(
        first_name="A",
        last_name="B",
        source="LinkedIn",
        desired_salary=75000,
        resume_url="https://resume.com/a",
        score=85.5,
    )
    result = _candidate_to_ghl_contact(c)
    cf = result["customFields"]
    assert cf["referral_source"] == "LinkedIn"
    assert cf["desired_salary"] == "75000"
    assert cf["resume_url"] == "https://resume.com/a"
    assert cf["interview_score"] == "85.5"


def test_candidate_to_ghl_contact_no_custom_fields():
    c = Candidate(first_name="A", last_name="B")
    result = _candidate_to_ghl_contact(c)
    assert "customFields" not in result


def test_ghl_contact_to_candidate_fields_basic():
    contact = {
        "firstName": "John",
        "lastName": "Smith",
        "email": "john@test.com",
        "phone": "+1234",
    }
    fields = _ghl_contact_to_candidate_fields(contact)
    assert fields["first_name"] == "John"
    assert fields["last_name"] == "Smith"
    assert fields["email"] == "john@test.com"
    assert fields["phone"] == "+1234"


def test_ghl_contact_to_candidate_fields_with_custom():
    contact = {
        "firstName": "A",
        "lastName": "B",
        "customFields": {
            "referral_source": "Indeed",
            "desired_salary": "60000",
            "resume_url": "https://r.com",
            "interview_score": "72",
        },
    }
    fields = _ghl_contact_to_candidate_fields(contact)
    assert fields["source"] == "Indeed"
    assert fields["desired_salary"] == 60000.0
    assert fields["resume_url"] == "https://r.com"
    assert fields["score"] == 72.0


def test_ghl_contact_to_candidate_fields_list_format():
    """GHL sometimes returns customFields as a list of {key, value} dicts."""
    contact = {
        "firstName": "A",
        "lastName": "B",
        "customFields": [
            {"key": "referral_source", "value": "Referral"},
        ],
    }
    fields = _ghl_contact_to_candidate_fields(contact)
    assert fields["source"] == "Referral"


@pytest.mark.asyncio
async def test_push_without_ghl_client(db: Session):
    """Push should gracefully handle missing GHL client."""
    db.add(Candidate(first_name="A", last_name="B"))
    db.commit()

    with patch.dict("sys.modules", {"maxlevel": None, "maxlevel.api": None}):
        result = await push_all_to_ghl(db)
    assert result["message"] == "GHL client not available"


@pytest.mark.asyncio
async def test_pull_without_ghl_client(db: Session):
    """Pull should gracefully handle missing GHL client."""
    with patch.dict("sys.modules", {"maxlevel": None, "maxlevel.api": None}):
        result = await pull_from_ghl(db)
    assert result["message"] == "GHL client not available"
