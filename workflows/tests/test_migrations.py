"""Smoke tests for workflows Alembic migrations."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from workflows.config import settings


def test_alembic_upgrade_creates_dispatch_table(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "wf_migrations.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{db_path}")

    repo_root = Path(__file__).resolve().parents[2]
    cfg = Config(str(repo_root / "workflows" / "alembic.ini"))
    command.upgrade(cfg, "head")

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    assert "workflow" in tables
    assert "workflow_dispatch" in tables
    assert "auth_account" in tables
    assert "auth_invite" in tables
    assert "auth_event" in tables
