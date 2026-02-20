"""Test fixtures for the Unified Dashboard — multi-DB setup with in-memory SQLite."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import DeclarativeBase

from dashboard.database import MultiDB


# --- CRM schema (minimal reproduction) ---

class CRMBase(DeclarativeBase):
    pass


class CRMContact(CRMBase):
    __tablename__ = "contact"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    location_id = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class CRMOpportunity(CRMBase):
    __tablename__ = "opportunity"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    location_id = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class CRMPipeline(CRMBase):
    __tablename__ = "pipeline"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    location_id = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class CRMActivity(CRMBase):
    __tablename__ = "activity"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_type = Column(String)
    entity_id = Column(String)
    action = Column(String)
    description = Column(Text)
    location_id = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class CRMAuthAccount(CRMBase):
    __tablename__ = "auth_account"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="viewer")
    is_active = Column(Boolean, default=True, nullable=False)
    invited_by_email = Column(String)
    last_login_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class CRMAuthEvent(CRMBase):
    __tablename__ = "auth_event"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    action = Column(String, index=True, nullable=False)
    outcome = Column(String, index=True, nullable=False)
    actor_email = Column(String, index=True)
    target_email = Column(String, index=True)
    source_ip = Column(String)
    user_agent = Column(String)
    details_json = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class CRMAuthSession(CRMBase):
    __tablename__ = "auth_session"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, index=True, nullable=False)
    source_ip = Column(String)
    user_agent = Column(String)
    expires_at = Column(DateTime, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, index=True)
    revoked_at = Column(DateTime, index=True)
    revoked_reason = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class CRMAuthPasswordReset(CRMBase):
    __tablename__ = "auth_password_reset"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, index=True, nullable=False)
    token_hash = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    used_at = Column(DateTime, index=True)
    source_ip = Column(String)
    user_agent = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


# --- Workflows schema (minimal reproduction) ---

class WFBase(DeclarativeBase):
    pass


class WFWorkflow(WFBase):
    __tablename__ = "workflow"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String)
    status = Column(String, default="draft")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class WFExecution(WFBase):
    __tablename__ = "workflow_execution"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id = Column(String)
    status = Column(String, default="completed")
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    steps_completed = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class WFLog(WFBase):
    __tablename__ = "workflow_log"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id = Column(String)
    execution_id = Column(String)
    level = Column(String, default="info")
    event = Column(String)
    message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


# --- Hiring schema uses sync SQLite ---

HIRING_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS position (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    department TEXT,
    status TEXT DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS candidate (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT,
    position_id INTEGER,
    stage TEXT DEFAULT 'Applied',
    status TEXT DEFAULT 'active',
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS candidateactivity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER,
    activity_type TEXT NOT NULL,
    description TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def multi_db():
    """Create 3 in-memory databases with minimal schemas and seed data."""
    # CRM (async)
    crm_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with crm_engine.begin() as conn:
        await conn.run_sync(CRMBase.metadata.create_all)

    # Workflows (async)
    wf_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with wf_engine.begin() as conn:
        await conn.run_sync(WFBase.metadata.create_all)

    # Hiring (sync)
    hiring_engine = create_engine("sqlite:///:memory:", echo=False)
    with hiring_engine.connect() as conn:
        for stmt in HIRING_TABLES_SQL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
        conn.commit()

    # Build MultiDB with test engines
    db = MultiDB.from_engines(crm_engine, wf_engine, hiring_engine)

    yield db

    await crm_engine.dispose()
    await wf_engine.dispose()
    hiring_engine.dispose()


@pytest_asyncio.fixture
async def seeded_db(multi_db):
    """Multi-DB with sample data seeded into all 3 databases."""
    now = datetime.utcnow()

    # Seed CRM
    async with multi_db.crm_session() as session:
        for i in range(5):
            session.add(CRMContact(id=str(uuid.uuid4()), location_id="loc1"))
        for i in range(3):
            session.add(CRMOpportunity(id=str(uuid.uuid4()), location_id="loc1"))
        session.add(CRMPipeline(id=str(uuid.uuid4()), location_id="loc1"))
        session.add(CRMPipeline(id=str(uuid.uuid4()), location_id="loc1"))
        for i in range(3):
            session.add(CRMActivity(
                id=str(uuid.uuid4()),
                entity_type="contact",
                entity_id=str(uuid.uuid4()),
                action="created",
                description=f"Contact {i} created",
                location_id="loc1",
                created_at=now - timedelta(hours=i),
            ))
        await session.commit()

    # Seed Workflows
    async with multi_db.wf_session() as session:
        wf_id = str(uuid.uuid4())
        session.add(WFWorkflow(id=wf_id, name="Test Workflow", status="published"))
        session.add(WFWorkflow(id=str(uuid.uuid4()), name="Draft WF", status="draft"))
        for i, status in enumerate(["completed", "completed", "failed"]):
            session.add(WFExecution(
                id=str(uuid.uuid4()),
                workflow_id=wf_id,
                status=status,
                steps_completed=i + 1,
            ))
        for i in range(2):
            session.add(WFLog(
                id=str(uuid.uuid4()),
                workflow_id=wf_id,
                level="info",
                event="step_completed",
                message=f"Step {i} completed",
                created_at=now - timedelta(hours=i + 5),
            ))
        await session.commit()

    # Seed Hiring
    with multi_db.hiring_connection() as conn:
        conn.execute(text(
            "INSERT INTO position (title, department, status) VALUES "
            "('Engineer', 'Dev', 'open'), ('Designer', 'Design', 'open'), "
            "('PM', 'Product', 'filled')"
        ))
        conn.execute(text(
            "INSERT INTO candidate (first_name, last_name, email, position_id, stage, status) VALUES "
            "('Alice', 'A', 'alice@test.com', 1, 'Applied', 'active'), "
            "('Bob', 'B', 'bob@test.com', 1, 'Screening', 'active'), "
            "('Carol', 'C', 'carol@test.com', 2, 'Hired', 'hired'), "
            "('Dave', 'D', 'dave@test.com', 1, 'Offer', 'active')"
        ))
        ts1 = (now - timedelta(hours=2)).isoformat()
        ts2 = (now - timedelta(hours=4)).isoformat()
        conn.execute(text(
            "INSERT INTO candidateactivity (candidate_id, activity_type, description, created_at) VALUES "
            f"(1, 'stage_change', 'Moved to Screening', '{ts1}'), "
            f"(3, 'stage_change', 'Hired!', '{ts2}')"
        ))
        conn.commit()

    return multi_db


@pytest_asyncio.fixture
async def client(seeded_db):
    """HTTPX async test client with MultiDB overridden to use seeded test databases."""
    import dashboard.database as db_module
    from dashboard.app import app

    original_db = db_module.multi_db
    db_module.multi_db = seeded_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    db_module.multi_db = original_db
