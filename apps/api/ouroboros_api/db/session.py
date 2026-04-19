"""Async SQLAlchemy engine + session factory. Local SQLite by default."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ..config import settings
from .models import Base

engine = create_async_engine(
    settings.db_url_resolved(),
    echo=False,
    future=True,
    connect_args={"check_same_thread": False} if "sqlite" in settings.db_url_resolved() else {},
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    """Create tables if absent. Alembic owns real migrations; this is a dev fallback."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    from ..seeds.bootstrap import bootstrap_if_empty

    await bootstrap_if_empty()


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
