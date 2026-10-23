"""Async SQLAlchemy engine/session setup, following the same class-based
dependency-injection style as SimulationRunner/VisionRunner/AnalyticsCollector
— a Database instance is constructed once in main.py::lifespan and stored on
app.state, not a module-level singleton.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from database.models import Base


class Database:
    def __init__(self, database_url: str):
        # An in-memory SQLite DB (used by tests) is per-connection by
        # default — StaticPool keeps one shared connection alive for the
        # engine's lifetime so create_all() and later sessions see the same
        # database. File-based SQLite/Postgres need no special pooling.
        kwargs: dict = {"echo": False}
        if ":memory:" in database_url:
            kwargs["connect_args"] = {"check_same_thread": False}
            kwargs["poolclass"] = StaticPool

        self.engine = create_async_engine(database_url, **kwargs)
        self.session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self.engine, expire_on_commit=False
        )

    async def init(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def dispose(self) -> None:
        await self.engine.dispose()
