"""SQLite database engine and session management."""

from __future__ import annotations

from sqlmodel import SQLModel, create_engine, Session

from .config import settings

engine = create_engine(f"sqlite:///{settings.db_path}", echo=False)


def create_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)


def get_db():
    """FastAPI dependency that yields a session."""
    with Session(engine) as session:
        yield session
