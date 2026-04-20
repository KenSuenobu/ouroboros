from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ouroboros_api.api import deps
from ouroboros_api.api import providers as providers_api
from ouroboros_api.db.models import Base, Provider, Workspace
from ouroboros_api.main import create_app


@pytest_asyncio.fixture
async def app_and_session(
    tmp_path: Path,
) -> AsyncIterator[tuple[object, async_sessionmaker[AsyncSession]]]:
    db_path = tmp_path / "provider-test.sqlite"
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
    try:
        yield app, session_factory
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


@pytest.mark.asyncio
async def test_create_provider_runs_health_probe_and_persists_result(
    app_and_session: tuple[object, async_sessionmaker[AsyncSession]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, session_factory = app_and_session

    async def fake_probe(_provider: Provider) -> tuple[str, str | None]:
        return "unauthorized", "invalid x-api-key"

    monkeypatch.setattr(providers_api, "_probe_health", fake_probe)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/providers",
            json={
                "name": "Anthropic",
                "kind": "anthropic",
                "base_url": "https://api.anthropic.com",
                "api_key": "bad-key",
                "config": {},
                "enabled": True,
            },
        )

    assert res.status_code == 201
    payload = res.json()
    assert payload["last_health_status"] == "unauthorized"
    assert payload["last_health_error"] == "invalid x-api-key"
    assert payload["last_health_checked_at"] is not None

    async with session_factory() as session:
        provider = await session.get(Provider, payload["id"])
        assert provider is not None
        assert provider.last_health_status == "unauthorized"
        assert provider.last_health_error == "invalid x-api-key"
        assert provider.last_health_checked_at is not None


@pytest.mark.asyncio
async def test_provider_health_endpoint_updates_persisted_result(
    app_and_session: tuple[object, async_sessionmaker[AsyncSession]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, session_factory = app_and_session
    async with session_factory() as session:
        ws = (await session.execute(select(Workspace).where(Workspace.slug == "default"))).scalar_one()
        provider = Provider(
            workspace_id=ws.id,
            name="Ollama",
            kind="ollama",
            base_url="http://localhost:11434",
        )
        session.add(provider)
        await session.commit()
        provider_id = provider.id

    async def fake_probe(_provider: Provider) -> tuple[str, str | None]:
        return "unreachable", "connection refused"

    monkeypatch.setattr(providers_api, "_probe_health", fake_probe)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(f"/api/providers/{provider_id}/health")

    assert res.status_code == 200
    payload = res.json()
    assert payload["provider_id"] == provider_id
    assert payload["status"] == "unreachable"
    assert payload["error"] == "connection refused"
    assert payload["checked_at"] is not None

    async with session_factory() as session:
        provider = await session.get(Provider, provider_id)
        assert provider is not None
        assert provider.last_health_status == "unreachable"
        assert provider.last_health_error == "connection refused"
        assert provider.last_health_checked_at is not None


@pytest.mark.asyncio
async def test_probe_health_marks_anthropic_401_as_unauthorized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        status_code = 401
        reason_phrase = "Unauthorized"
        text = '{"error":"invalid x-api-key"}'

    class FakeClient:
        async def __aenter__(self) -> FakeClient:
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def head(self, _path: str) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(providers_api.httpx, "AsyncClient", lambda **_: FakeClient())

    provider = Provider(
        id="provider-id",
        workspace_id="workspace-id",
        name="Anthropic",
        kind="anthropic",
        base_url="https://api.anthropic.com",
        config={},
        enabled=True,
    )
    status, error = await providers_api._probe_health(provider)

    assert status == "unauthorized"
    assert error is not None
    assert "invalid x-api-key" in error
