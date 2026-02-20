"""Workflow Builder configuration via pydantic-settings."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings


class WorkflowSettings(BaseSettings):
    environment: str = "development"
    database_url: str = "sqlite+aiosqlite:///workflows.db"
    echo_sql: bool = False
    app_title: str = "MaxLevel Workflows"
    auth_enabled: bool = False
    auth_secret: str = ""
    auth_cookie_name: str = "ml_wf_session"
    auth_cookie_secure: bool = False
    auth_session_ttl_seconds: int = 86400
    auth_rate_limit_window_seconds: int = 300
    auth_rate_limit_max_attempts: int = 10
    auth_rate_limit_block_seconds: int = 600
    auth_invite_ttl_hours: int = 72
    auth_bootstrap_email: str = "admin@example.com"
    auth_bootstrap_password: str = ""
    auth_bootstrap_role: str = "owner"
    anthropic_api_key: str = ""
    security_fail_closed: bool = False
    webhook_api_key: str = ""
    webhook_signing_secret: str = ""
    webhook_signature_ttl_seconds: int = 300
    chat_api_key: str = ""
    webhook_async_dispatch: bool = True
    dispatch_worker_enabled: bool = True
    dispatch_poll_interval_seconds: float = 1.0
    dispatch_max_attempts: int = 3
    dispatch_retry_backoff_seconds: int = 15
    dashboard_url: str = "http://localhost:8023"
    crm_url: str = "http://localhost:8020"
    hiring_url: str = "http://localhost:8021"
    workflows_url: str = "http://localhost:8022"

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

    @property
    def app_urls(self) -> dict[str, str]:
        return {
            "dashboard": self.dashboard_url,
            "crm": self.crm_url,
            "hiring": self.hiring_url,
            "workflows": self.workflows_url,
        }

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() in {"prod", "production"}


settings = WorkflowSettings()
