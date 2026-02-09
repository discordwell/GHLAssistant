"""Tests for best-effort workflow fidelity parsing."""

from __future__ import annotations

import pytest

from crm.sync.export_workflows import parse_workflow_steps


def test_parse_workflow_steps_fidelity_1_returns_empty():
    payload = {"workflow": {"name": "X", "actions": [{"type": "sms", "message": "hi"}]}}
    assert parse_workflow_steps(payload, fidelity=1) == []


def test_parse_workflow_steps_extracts_linear_actions():
    payload = {
        "workflow": {
            "name": "X",
            "actions": [
                {"type": "send_sms", "message": "Hello"},
                {"type": "wait", "minutes": 2},
                {"type": "add_tag", "tagName": "New Lead"},
                {"type": "send_email", "subject": "Welcome", "body": "Thanks"},
            ],
        }
    }

    steps = parse_workflow_steps(payload, fidelity=2)
    kinds = [s.kind for s in steps]
    assert "send_sms" in kinds
    assert "delay" in kinds
    assert "add_tag" in kinds
    assert "send_email" in kinds

