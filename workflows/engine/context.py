"""Execution context — variable passing between steps."""

from __future__ import annotations

import re
from typing import Any


class ExecutionContext:
    """Holds runtime state for a workflow execution.

    Provides variable substitution using {{variable}} syntax.
    Variables are populated from trigger data, step outputs, and contact info.
    """

    def __init__(self, trigger_data: dict | None = None):
        self._data: dict[str, Any] = {}
        if trigger_data:
            self._data["trigger"] = trigger_data
            # Flatten contact data to top level for easy access
            if "contact" in trigger_data:
                self._data["contact"] = trigger_data["contact"]

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get value by dotted key path (e.g. 'contact.first_name')."""
        parts = key.split(".")
        current = self._data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return default
            if current is None:
                return default
        return current

    def set_step_output(self, step_id: str, output: dict) -> None:
        """Store output from a completed step."""
        steps = self._data.setdefault("steps", {})
        steps[step_id] = output

    def resolve_template(self, text: str) -> str:
        """Replace {{variable}} placeholders with context values."""
        def replacer(match):
            key = match.group(1).strip()
            value = self.get(key)
            return str(value) if value is not None else match.group(0)

        return re.sub(r"\{\{(.+?)\}\}", replacer, text)

    def resolve_config(self, config: dict) -> dict:
        """Deep-resolve all string values in a config dict."""
        resolved = {}
        for key, value in config.items():
            if isinstance(value, str):
                resolved[key] = self.resolve_template(value)
            elif isinstance(value, dict):
                resolved[key] = self.resolve_config(value)
            elif isinstance(value, list):
                resolved[key] = [
                    self.resolve_template(v) if isinstance(v, str) else v
                    for v in value
                ]
            else:
                resolved[key] = value
        return resolved

    def to_dict(self) -> dict:
        return dict(self._data)
