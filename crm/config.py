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

    # Browser fallback export planning for API-limited resources
    sync_browser_fallback_enabled: bool = True
    sync_browser_tab_id: int = 0
    sync_browser_execute_enabled: bool = False
    sync_browser_profile: str = "ghl_session"
    sync_browser_headless: bool = False
    sync_browser_continue_on_error: bool = True
    sync_browser_find_attempts: int = 3
    sync_browser_step_retry_wait_seconds: float = 0.75
    sync_browser_require_login: bool = True
    sync_browser_preflight_url: str = "https://app.gohighlevel.com/"
    sync_browser_login_email: str | None = None
    sync_browser_login_password: str | None = None
    sync_browser_login_timeout_seconds: int = 120
    sync_workflow_fidelity: int = 2

    # Assets (media library + attachments)
    sync_assets_enabled: bool = True
    # Media Library can be huge; keep off by default unless explicitly enabled.
    sync_assets_import_media_library: bool = False
    sync_assets_media_library_page_size: int = 200
    sync_assets_media_library_max_pages: int = 25
    # Archiving full media library listings can create massive files; default to summary-only.
    sync_assets_media_library_archive_full: bool = False
    sync_assets_media_library_archive_sample: int = 50
    sync_assets_download_during_import: bool = False
    sync_assets_download_limit: int = 200
    # Export: upload local/discovered assets into GHL Media Library (requires `token-id` from browser capture).
    sync_assets_export_enabled: bool = False
    sync_assets_export_limit: int = 50
    # Comma-separated Asset.source values to upload (default: funnel-page assets only).
    sync_assets_export_sources: str = "funnel_page_data_uri,funnel_page_html"

    asset_blobstore_dir: str = "data/blobstore"

    model_config = {"env_prefix": "CRM_", "env_file": ".env", "extra": "ignore"}

    @property
    def base_dir(self) -> Path:
        return Path(__file__).resolve().parent

    @property
    def project_dir(self) -> Path:
        return self.base_dir.parent

    @property
    def data_dir(self) -> Path:
        return self.project_dir / "data"

    @property
    def blobstore_dir(self) -> Path:
        path = Path(self.asset_blobstore_dir)
        if not path.is_absolute():
            path = self.project_dir / path
        return path

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
