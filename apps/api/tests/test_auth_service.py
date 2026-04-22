"""Unit tests for password hashing + session lifecycle."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ouroboros_api.db.models import Base, User
from ouroboros_api.services import auth as auth_svc


@pytest_asyncio.fixture
async def db(tmp_path: Path) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'auth-svc.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session
    await engine.dispose()


def test_hash_and_verify_password() -> None:
    h = auth_svc.hash_password("hunter2")
    assert h.startswith("$argon2")
    assert auth_svc.verify_password("hunter2", h)
    assert not auth_svc.verify_password("wrong", h)
    assert not auth_svc.verify_password("hunter2", None)
    assert not auth_svc.verify_password("", h)


def test_hash_password_rejects_empty() -> None:
    with pytest.raises(ValueError):
        auth_svc.hash_password("")


@pytest.mark.asyncio
async def test_create_and_resolve_session(db: AsyncSession) -> None:
    user = User(email="alice@example.com", display_name="Alice", is_active=True)
    db.add(user)
    await db.commit()

    raw, session = await auth_svc.create_session(db, user, ip="127.0.0.1", user_agent="pytest")
    await db.commit()

    assert raw and len(raw) > 32
    assert session.user_id == user.id
    assert session.id != raw  # stored hash, not the raw token

    resolved = await auth_svc.resolve_session(db, raw)
    assert resolved is not None
    sess, resolved_user = resolved
    assert resolved_user.id == user.id
    assert sess.id == session.id


@pytest.mark.asyncio
async def test_resolve_session_rejects_unknown_or_inactive(db: AsyncSession) -> None:
    user = User(email="bob@example.com", display_name="Bob", is_active=False)
    db.add(user)
    await db.commit()
    raw, _ = await auth_svc.create_session(db, user)
    await db.commit()

    assert await auth_svc.resolve_session(db, raw) is None
    assert await auth_svc.resolve_session(db, "garbage-token") is None
    assert await auth_svc.resolve_session(db, "") is None


@pytest.mark.asyncio
async def test_resolve_session_drops_expired(db: AsyncSession) -> None:
    user = User(email="cara@example.com", display_name="Cara", is_active=True)
    db.add(user)
    await db.commit()
    raw, session = await auth_svc.create_session(db, user)
    session.expires_at = auth_svc._now() - timedelta(seconds=1)
    await db.commit()

    assert await auth_svc.resolve_session(db, raw) is None


@pytest.mark.asyncio
async def test_revoke_session_invalidates_token(db: AsyncSession) -> None:
    user = User(email="dan@example.com", display_name="Dan", is_active=True)
    db.add(user)
    await db.commit()
    raw, _ = await auth_svc.create_session(db, user)
    await db.commit()

    await auth_svc.revoke_session(db, raw)
    await db.commit()
    assert await auth_svc.resolve_session(db, raw) is None
