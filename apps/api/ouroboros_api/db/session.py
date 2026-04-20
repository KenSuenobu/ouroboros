"""Async SQLAlchemy engine + session factory. Local SQLite by default."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from pathlib import Path

from alembic import command
from alembic.config import Config

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ..config import settings
from .models import Base

log = logging.getLogger("ouroboros.db")

engine = create_async_engine(
    settings.db_url_resolved(),
    echo=False,
    future=True,
    connect_args={"check_same_thread": False} if "sqlite" in settings.db_url_resolved() else {},
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _run_migrations_to_head() -> None:
    """Apply all Alembic revisions before the app serves requests."""
    alembic_ini = Path(__file__).resolve().parents[2] / "alembic.ini"
    cfg = Config(str(alembic_ini))
    command.upgrade(cfg, "head")


async def init_db() -> None:
    """Ensure schema is current, then seed defaults when the DB is empty."""
    try:
        await asyncio.to_thread(_run_migrations_to_head)
    except Exception:  # pragma: no cover - fallback path is defensive
        # Keep local/dev startup usable even when migration config is unavailable.
        log.exception("alembic upgrade failed, falling back to metadata.create_all")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    from ..seeds.bootstrap import bootstrap_if_empty

    await bootstrap_if_empty()


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
