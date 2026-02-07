"""Dashboard configuration via pydantic-settings."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings


class DashboardSettings(BaseSettings):
    crm_database_url: str = "sqlite+aiosqlite:///crm.db"
    wf_database_url: str = "sqlite+aiosqlite:///workflows.db"
    hiring_database_url: str = "sqlite:///hiring.db"
    app_title: str = "MaxLevel Dashboard"

    model_config = {"env_prefix": "DASH_", "env_file": ".env", "extra": "ignore"}

    @property
    def base_dir(self) -> Path:
        return Path(__file__).resolve().parent

    @property
    def templates_dir(self) -> Path:
        return self.base_dir / "templates"

    @property
    def static_dir(self) -> Path:
        return self.base_dir / "static"


settings = DashboardSettings()
