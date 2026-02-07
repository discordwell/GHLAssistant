"""Multi-database read-only access to CRM, Workflows, and Hiring databases."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from .config import settings


class MultiDB:
    """Read-only connection factories for all 3 app databases."""

    def __init__(
        self,
        crm_url: str | None = None,
        wf_url: str | None = None,
        hiring_url: str | None = None,
    ):
        self.crm_engine: AsyncEngine = create_async_engine(
            crm_url or settings.crm_database_url, echo=False
        )
        self.wf_engine: AsyncEngine = create_async_engine(
            wf_url or settings.wf_database_url, echo=False
        )
        # Hiring uses sync SQLite
        self.hiring_engine: Engine = create_engine(
            hiring_url or settings.hiring_database_url, echo=False
        )

        self._crm_session = async_sessionmaker(
            self.crm_engine, class_=AsyncSession, expire_on_commit=False
        )
        self._wf_session = async_sessionmaker(
            self.wf_engine, class_=AsyncSession, expire_on_commit=False
        )

    @classmethod
    def from_engines(
        cls, crm_engine: AsyncEngine, wf_engine: AsyncEngine, hiring_engine: Engine
    ) -> MultiDB:
        """Create a MultiDB from pre-built engines (useful for testing)."""
        db = cls.__new__(cls)
        db.crm_engine = crm_engine
        db.wf_engine = wf_engine
        db.hiring_engine = hiring_engine
        db._crm_session = async_sessionmaker(crm_engine, class_=AsyncSession, expire_on_commit=False)
        db._wf_session = async_sessionmaker(wf_engine, class_=AsyncSession, expire_on_commit=False)
        return db

    def crm_session(self) -> AsyncSession:
        return self._crm_session()

    def wf_session(self) -> AsyncSession:
        return self._wf_session()

    def hiring_connection(self):
        return self.hiring_engine.connect()

    async def dispose(self):
        await self.crm_engine.dispose()
        await self.wf_engine.dispose()
        self.hiring_engine.dispose()


multi_db = MultiDB()
