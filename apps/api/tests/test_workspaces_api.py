from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ouroboros_api.api import deps
from ouroboros_api.main import create_app
from ouroboros_api.db.models import Base, Project, Provider, Workspace


@pytest_asyncio.fixture
async def app_and_session(
    tmp_path: Path,
) -> AsyncIterator[tuple[object, async_sessionmaker[AsyncSession]]]:
    db_path = tmp_path / "workspace-test.sqlite"
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
async def test_workspace_me_requires_onboarding_when_empty(
    app_and_session: tuple[object, async_sessionmaker[AsyncSession]],
) -> None:
    app, _ = app_and_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/workspaces/me")

    assert res.status_code == 200
    payload = res.json()
    assert payload["project_count"] == 0
    assert payload["provider_count"] == 0
    assert payload["requires_onboarding"] is True
    assert payload["onboarding_completed_at"] is None


@pytest.mark.asyncio
async def test_workspace_me_does_not_require_onboarding_after_minimum_entities_exist(
    app_and_session: tuple[object, async_sessionmaker[AsyncSession]],
) -> None:
    app, session_factory = app_and_session
    async with session_factory() as session:
        ws = (await session.execute(select(Workspace).where(Workspace.slug == "default"))).scalar_one()
        assert ws is not None
        workspace_id = ws.id
        session.add(
            Project(
                workspace_id=workspace_id,
                name="Demo",
                repo_url="https://github.com/acme/demo",
                scm_kind="github",
                default_branch="main",
            )
        )
        session.add(Provider(workspace_id=workspace_id, name="Ollama", kind="ollama"))
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/workspaces/me")

    assert res.status_code == 200
    payload = res.json()
    assert payload["project_count"] == 1
    assert payload["provider_count"] == 1
    assert payload["requires_onboarding"] is False
    assert payload["onboarding_completed_at"] is None


@pytest.mark.asyncio
async def test_workspace_onboarding_endpoint_marks_completion_and_updates_name(
    app_and_session: tuple[object, async_sessionmaker[AsyncSession]],
) -> None:
    app, _ = app_and_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/workspaces/me/onboarding",
            json={"name": "Team Phoenix"},
        )

    assert res.status_code == 200
    payload = res.json()
    assert payload["name"] == "Team Phoenix"
    assert payload["requires_onboarding"] is False
    assert payload["onboarding_completed_at"] is not None
