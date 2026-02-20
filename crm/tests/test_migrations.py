"""Smoke tests for CRM Alembic migrations."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from crm.config import settings


def test_alembic_upgrade_creates_auth_tables(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "crm_migrations.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{db_path}")

    repo_root = Path(__file__).resolve().parents[2]
    cfg = Config(str(repo_root / "crm" / "alembic.ini"))
    # CRM base migrations use PostgreSQL-specific types; for SQLite smoke testing
    # this revision, stamp just before auth migrations and apply this revision only.
    command.stamp(cfg, "f8ab85f63219")
    command.upgrade(cfg, "006_auth_events")

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    assert "auth_account" in tables
    assert "auth_invite" in tables
    assert "auth_event" in tables
