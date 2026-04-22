from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ouroboros_api.api import deps
from ouroboros_api.api import projects as projects_api
from ouroboros_api.config import settings
from ouroboros_api.db.models import Base, Workspace
from ouroboros_api.main import create_app

from ._auth import install_test_admin


@pytest_asyncio.fixture
async def app_and_session(
    tmp_path: Path,
) -> AsyncIterator[tuple[object, async_sessionmaker[AsyncSession]]]:
    db_path = tmp_path / "projects-oauth.sqlite"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        session.add(Workspace(slug="default", name="Default Workspace"))
        await session.commit()

    app = create_app()

    @asynccontextmanager
    async def noop_lifespan(_app: object) -> AsyncIterator[None]:
        yield

    app.router.lifespan_context = noop_lifespan  # type: ignore[method-assign]

    async def override_db_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[deps.db_session] = override_db_session
    await install_test_admin(app, session_factory)
    try:
        yield app, session_factory
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, object]) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self) -> dict[str, object]:
        return self._payload


@pytest.mark.asyncio
async def test_github_device_oauth_start_and_poll(
    app_and_session: tuple[object, async_sessionmaker[AsyncSession]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, _ = app_and_session

    class FakeHttpClient:
        async def __aenter__(self) -> FakeHttpClient:
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def post(
            self, url: str, data: dict[str, str], headers: dict[str, str]
        ) -> _FakeResponse:
            assert headers.get("Accept") == "application/json"
            if url.endswith("/device/code"):
                assert data["scope"] == settings.github_oauth_scope
                return _FakeResponse(
                    200,
                    {
                        "device_code": "device-123",
                        "user_code": "ABCD-EFGH",
                        "verification_uri": "https://github.com/login/device",
                        "expires_in": 900,
                        "interval": 5,
                    },
                )
            if url.endswith("/access_token"):
                return _FakeResponse(
                    200,
                    {
                        "access_token": "oauth-token-xyz",
                        "token_type": "bearer",
                        "scope": "repo",
                    },
                )
            return _FakeResponse(404, {"error": "not-found"})

    monkeypatch.setattr(projects_api.httpx, "AsyncClient", lambda **_: FakeHttpClient())
    original_client_id = settings.github_oauth_client_id
    settings.github_oauth_client_id = "client-id-123"

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            start = await client.post(
                "/api/projects/oauth/github/device/start",
                json={"repo_url": "https://github.com/acme/private-repo"},
            )
            assert start.status_code == 200
            start_payload = start.json()
            assert start_payload["device_code"] == "device-123"
            assert start_payload["user_code"] == "ABCD-EFGH"

            poll = await client.post(
                "/api/projects/oauth/github/device/poll",
                json={"device_code": start_payload["device_code"]},
            )
            assert poll.status_code == 200
            poll_payload = poll.json()
            assert poll_payload["status"] == "authorized"
            assert poll_payload["access_token"] == "oauth-token-xyz"
    finally:
        settings.github_oauth_client_id = original_client_id


@pytest.mark.asyncio
async def test_github_device_oauth_start_requires_github_repo_url(
    app_and_session: tuple[object, async_sessionmaker[AsyncSession]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, _ = app_and_session

    original_client_id = settings.github_oauth_client_id
    settings.github_oauth_client_id = "client-id-123"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            start = await client.post(
                "/api/projects/oauth/github/device/start",
                json={"repo_url": "https://gitlab.com/acme/private-repo"},
            )
        assert start.status_code == 400
        assert "GitHub repository URLs" in start.text
    finally:
        settings.github_oauth_client_id = original_client_id
