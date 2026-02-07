"""Condition expression evaluator for workflow branching."""

from __future__ import annotations

import operator
from typing import Any

from .context import ExecutionContext

# Supported operators
OPERATORS = {
    "equals": operator.eq,
    "not_equals": operator.ne,
    "contains": lambda a, b: b in str(a) if a else False,
    "not_contains": lambda a, b: b not in str(a) if a else True,
    "starts_with": lambda a, b: str(a).startswith(str(b)) if a else False,
    "ends_with": lambda a, b: str(a).endswith(str(b)) if a else False,
    "greater_than": lambda a, b: float(a) > float(b) if a is not None else False,
    "less_than": lambda a, b: float(a) < float(b) if a is not None else False,
    "is_empty": lambda a, _: not a,
    "is_not_empty": lambda a, _: bool(a),
    "exists": lambda a, _: a is not None,
}


def evaluate_condition(config: dict, ctx: ExecutionContext) -> bool:
    """Evaluate a condition config against execution context.

    Config format:
        {
            "field": "contact.tags",
            "operator": "contains",
            "value": "VIP"
        }

    Or for compound conditions:
        {
            "logic": "and",  # or "or"
            "conditions": [
                {"field": "...", "operator": "...", "value": "..."},
                ...
            ]
        }
    """
    if not config:
        return True

    # Compound condition
    if "logic" in config and "conditions" in config:
        results = [evaluate_condition(c, ctx) for c in config["conditions"]]
        if config["logic"] == "or":
            return any(results)
        return all(results)  # default to AND

    # Simple condition
    field = config.get("field", "")
    op_name = config.get("operator", "equals")
    expected = config.get("value", "")

    # Resolve field from context
    actual = ctx.get(field)

    # Resolve template in expected value
    if isinstance(expected, str) and "{{" in expected:
        expected = ctx.resolve_template(expected)

    # Get operator function
    op_func = OPERATORS.get(op_name, operator.eq)

    try:
        return op_func(actual, expected)
    except (TypeError, ValueError):
        return False
