"""Hiring tool configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_STAGES: list[str] = [
    "Applied",
    "Screening",
    "Phone Interview",
    "In-Person Interview",
    "Background Check",
    "Offer",
    "Hired",
    "Rejected",
]


@dataclass
class Settings:
    db_path: str = os.environ.get("HIRING_DB_PATH", "hiring.db")
    sync_interval_seconds: int = int(os.environ.get("HIRING_SYNC_INTERVAL", "300"))
    stages: list[str] = field(default_factory=lambda: list(DEFAULT_STAGES))
    ghl_pipeline_name: str = "Hiring Pipeline"
    dashboard_url: str = os.environ.get("HIRING_DASHBOARD_URL", "http://localhost:8023")
    crm_url: str = os.environ.get("HIRING_CRM_URL", "http://localhost:8020")
    hiring_url: str = os.environ.get("HIRING_APP_URL", "http://localhost:8021")
    workflows_url: str = os.environ.get("HIRING_WORKFLOWS_URL", "http://localhost:8022")
    base_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent)

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


settings = Settings()
