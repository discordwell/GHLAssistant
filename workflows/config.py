"""Workflow Builder configuration via pydantic-settings."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings


class WorkflowSettings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///workflows.db"
    echo_sql: bool = False
    app_title: str = "MaxLevel Workflows"
    anthropic_api_key: str = ""

    model_config = {"env_prefix": "WF_", "env_file": ".env", "extra": "ignore"}

    @property
    def base_dir(self) -> Path:
        return Path(__file__).resolve().parent

    @property
    def templates_dir(self) -> Path:
        return self.base_dir / "templates"

    @property
    def static_dir(self) -> Path:
        return self.base_dir / "static"


settings = WorkflowSettings()
