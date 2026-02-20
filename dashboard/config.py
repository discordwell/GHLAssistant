"""Dashboard configuration via pydantic-settings."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings


class DashboardSettings(BaseSettings):
    crm_database_url: str = "sqlite+aiosqlite:///crm.db"
    wf_database_url: str = "sqlite+aiosqlite:///workflows.db"
    hiring_database_url: str = "sqlite:///hiring.db"
    app_title: str = "MaxLevel Dashboard"
    auth_enabled: bool = False
    auth_secret: str = ""
    auth_cookie_name: str = "ml_dash_session"
    auth_cookie_secure: bool = False
    auth_session_ttl_seconds: int = 86400
    auth_bootstrap_email: str = "admin@example.com"
    auth_bootstrap_password: str = ""
    auth_bootstrap_role: str = "owner"
    dashboard_url: str = "http://localhost:8023"
    crm_url: str = "http://localhost:8020"
    hiring_url: str = "http://localhost:8021"
    workflows_url: str = "http://localhost:8022"

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

    @property
    def app_urls(self) -> dict[str, str]:
        return {
            "dashboard": self.dashboard_url,
            "crm": self.crm_url,
            "hiring": self.hiring_url,
            "workflows": self.workflows_url,
        }


settings = DashboardSettings()
