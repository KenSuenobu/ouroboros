"""WebSocket auth tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.websockets import WebSocketDisconnect

from ouroboros_api.config import settings
from ouroboros_api.db import session as session_module
from ouroboros_api.db.models import Base, User, Workspace
from ouroboros_api.main import create_app
from ouroboros_api.services import auth as auth_svc


@pytest_asyncio.fixture
async def stack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[tuple[object, str]]:
    db_path = tmp_path / "ws-auth.sqlite"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    monkeypatch.setattr(session_module, "SessionLocal", factory)

    async with factory() as session:
        ws = Workspace(slug="default", name="Default Workspace")
        session.add(ws)
        await session.flush()
        u = User(
            email="ws@example.com",
            display_name="WS",
            password_hash=auth_svc.hash_password("password1"),
            is_active=True,
        )
        session.add(u)
        await session.flush()
        token, _ = await auth_svc.create_session(session, u)
        await session.commit()

    app = create_app()

    @asynccontextmanager
    async def noop_lifespan(_app):
        yield

    app.router.lifespan_context = noop_lifespan  # type: ignore[method-assign]

    yield app, token
    await engine.dispose()


def test_ws_rejects_unauthenticated(stack) -> None:
    app, _ = stack
    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/runs"):
            pass


def test_ws_accepts_with_token(stack) -> None:
    app, token = stack
    client = TestClient(app)
    with client.websocket_connect(f"/ws/runs?token={token}") as websocket:
        # The connection should be accepted; the bus may not emit immediately
        # so we just verify accept() worked by sending no data and closing.
        websocket.close()


def test_ws_accepts_with_cookie(stack) -> None:
    app, token = stack
    client = TestClient(app)
    client.cookies.set(settings.auth_session_cookie_name, token)
    with client.websocket_connect("/ws/runs") as websocket:
        websocket.close()
