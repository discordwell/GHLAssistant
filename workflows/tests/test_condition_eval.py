"""Tests for the condition expression evaluator."""

from __future__ import annotations

import pytest

from workflows.engine.context import ExecutionContext
from workflows.engine.evaluator import evaluate_condition


class TestEvaluator:
    def test_equals(self):
        ctx = ExecutionContext({"name": "John"})
        assert evaluate_condition({"field": "trigger.name", "operator": "equals", "value": "John"}, ctx) is True
        assert evaluate_condition({"field": "trigger.name", "operator": "equals", "value": "Jane"}, ctx) is False

    def test_not_equals(self):
        ctx = ExecutionContext({"status": "active"})
        assert evaluate_condition({"field": "trigger.status", "operator": "not_equals", "value": "inactive"}, ctx) is True

    def test_contains(self):
        ctx = ExecutionContext({"tags": "VIP, Premium"})
        assert evaluate_condition({"field": "trigger.tags", "operator": "contains", "value": "VIP"}, ctx) is True
        assert evaluate_condition({"field": "trigger.tags", "operator": "contains", "value": "Basic"}, ctx) is False

    def test_not_contains(self):
        ctx = ExecutionContext({"tags": "VIP"})
        assert evaluate_condition({"field": "trigger.tags", "operator": "not_contains", "value": "Basic"}, ctx) is True

    def test_starts_with(self):
        ctx = ExecutionContext({"email": "john@example.com"})
        assert evaluate_condition({"field": "trigger.email", "operator": "starts_with", "value": "john"}, ctx) is True

    def test_ends_with(self):
        ctx = ExecutionContext({"email": "john@example.com"})
        assert evaluate_condition({"field": "trigger.email", "operator": "ends_with", "value": ".com"}, ctx) is True

    def test_greater_than(self):
        ctx = ExecutionContext({"score": 85})
        assert evaluate_condition({"field": "trigger.score", "operator": "greater_than", "value": 50}, ctx) is True
        assert evaluate_condition({"field": "trigger.score", "operator": "greater_than", "value": 90}, ctx) is False

    def test_less_than(self):
        ctx = ExecutionContext({"score": 30})
        assert evaluate_condition({"field": "trigger.score", "operator": "less_than", "value": 50}, ctx) is True

    def test_is_empty(self):
        ctx = ExecutionContext({"name": "", "value": "x"})
        assert evaluate_condition({"field": "trigger.name", "operator": "is_empty", "value": ""}, ctx) is True
        assert evaluate_condition({"field": "trigger.value", "operator": "is_empty", "value": ""}, ctx) is False

    def test_is_not_empty(self):
        ctx = ExecutionContext({"name": "John"})
        assert evaluate_condition({"field": "trigger.name", "operator": "is_not_empty", "value": ""}, ctx) is True

    def test_exists(self):
        ctx = ExecutionContext({"name": "John"})
        assert evaluate_condition({"field": "trigger.name", "operator": "exists", "value": ""}, ctx) is True
        assert evaluate_condition({"field": "trigger.missing", "operator": "exists", "value": ""}, ctx) is False

    def test_compound_and(self):
        ctx = ExecutionContext({"name": "John", "score": 85})
        cond = {
            "logic": "and",
            "conditions": [
                {"field": "trigger.name", "operator": "equals", "value": "John"},
                {"field": "trigger.score", "operator": "greater_than", "value": 50},
            ],
        }
        assert evaluate_condition(cond, ctx) is True

    def test_compound_or(self):
        ctx = ExecutionContext({"name": "Jane", "score": 85})
        cond = {
            "logic": "or",
            "conditions": [
                {"field": "trigger.name", "operator": "equals", "value": "John"},
                {"field": "trigger.score", "operator": "greater_than", "value": 50},
            ],
        }
        assert evaluate_condition(cond, ctx) is True

    def test_empty_config_returns_true(self):
        ctx = ExecutionContext()
        assert evaluate_condition({}, ctx) is True

    def test_none_field_handling(self):
        ctx = ExecutionContext({})
        assert evaluate_condition({"field": "missing.field", "operator": "equals", "value": "x"}, ctx) is False


class TestExecutionContext:
    def test_dotted_get(self):
        ctx = ExecutionContext({"contact": {"first_name": "John", "tags": ["VIP"]}})
        assert ctx.get("contact.first_name") == "John"
        assert ctx.get("contact.tags") == ["VIP"]

    def test_resolve_template(self):
        ctx = ExecutionContext({"contact": {"first_name": "John"}})
        result = ctx.resolve_template("Hello {{contact.first_name}}!")
        assert result == "Hello John!"

    def test_resolve_template_missing(self):
        ctx = ExecutionContext({})
        result = ctx.resolve_template("Hello {{contact.first_name}}!")
        assert result == "Hello {{contact.first_name}}!"

    def test_step_output(self):
        ctx = ExecutionContext()
        ctx.set_step_output("step-1", {"result": "ok"})
        assert ctx.get("steps.step-1.result") == "ok"

    def test_resolve_config(self):
        ctx = ExecutionContext({"contact": {"first_name": "John"}})
        config = {"message": "Hi {{contact.first_name}}", "count": 5}
        resolved = ctx.resolve_config(config)
        assert resolved["message"] == "Hi John"
        assert resolved["count"] == 5
