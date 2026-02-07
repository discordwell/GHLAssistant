"""CRM configuration via pydantic-settings."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings


class CRMSettings(BaseSettings):
    database_url: str = "postgresql+asyncpg://localhost/crm"
    echo_sql: bool = False
    app_title: str = "CRM Platform"

    model_config = {"env_prefix": "CRM_", "env_file": ".env", "extra": "ignore"}

    @property
    def base_dir(self) -> Path:
        return Path(__file__).resolve().parent

    @property
    def templates_dir(self) -> Path:
        return self.base_dir / "templates"

    @property
    def static_dir(self) -> Path:
        return self.base_dir / "static"


settings = CRMSettings()
