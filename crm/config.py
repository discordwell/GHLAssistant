"""CRM configuration via pydantic-settings."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings


class CRMSettings(BaseSettings):
    database_url: str = "postgresql+asyncpg://localhost/crm"
    echo_sql: bool = False
    app_title: str = "CRM Platform"

    # Twilio (optional — SMS)
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from_number: str | None = None

    # SendGrid (optional — Email)
    sendgrid_api_key: str | None = None
    sendgrid_from_email: str | None = None
    sendgrid_from_name: str | None = None

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

    @property
    def twilio_configured(self) -> bool:
        return bool(self.twilio_account_sid and self.twilio_auth_token and self.twilio_from_number)

    @property
    def sendgrid_configured(self) -> bool:
        return bool(self.sendgrid_api_key and self.sendgrid_from_email)


settings = CRMSettings()
