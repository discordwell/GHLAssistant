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
    base_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent)

    @property
    def templates_dir(self) -> Path:
        return self.base_dir / "templates"

    @property
    def static_dir(self) -> Path:
        return self.base_dir / "static"


settings = Settings()
