from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ouroboros_api.api import deps
from ouroboros_api.db.models import Base, Project, Workspace
from ouroboros_api.main import create_app


@pytest_asyncio.fixture
async def app_and_session(
    tmp_path: Path,
) -> AsyncIterator[tuple[object, async_sessionmaker[AsyncSession]]]:
    db_path = tmp_path / "projects-introspect.sqlite"
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
async def test_project_introspect_suggests_from_package_and_pyproject(
    app_and_session: tuple[object, async_sessionmaker[AsyncSession]],
    tmp_path: Path,
) -> None:
    app, session_factory = app_and_session

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "package.json").write_text(
        json.dumps({"scripts": {"build": "next build", "test": "vitest"}}),
        encoding="utf-8",
    )
    (repo / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\naddopts = \"-q\"\n",
        encoding="utf-8",
    )

    async with session_factory() as session:
        workspace = (
            await session.execute(select(Workspace).where(Workspace.slug == "default"))
        ).scalar_one()
        project = Project(
            workspace_id=workspace.id,
            name="Demo",
            repo_url="https://github.com/acme/demo",
            scm_kind="github",
            default_branch="main",
            local_clone_hint=str(repo),
        )
        session.add(project)
        await session.commit()
        await session.refresh(project)
        project_id = project.id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(f"/api/projects/{project_id}/introspect")

    assert res.status_code == 200
    payload = res.json()
    assert "next build" in payload["build"]
    assert "vitest run" in payload["test"]
    assert "uv run pytest -q" in payload["test"]


@pytest.mark.asyncio
async def test_project_introspect_returns_empty_when_no_known_manifests(
    app_and_session: tuple[object, async_sessionmaker[AsyncSession]],
    tmp_path: Path,
) -> None:
    app, session_factory = app_and_session

    repo = tmp_path / "repo-empty"
    repo.mkdir()
    (repo / "README.md").write_text("# Empty\n", encoding="utf-8")

    async with session_factory() as session:
        workspace = (
            await session.execute(select(Workspace).where(Workspace.slug == "default"))
        ).scalar_one()
        project = Project(
            workspace_id=workspace.id,
            name="No Manifest",
            repo_url="https://github.com/acme/no-manifest",
            scm_kind="github",
            default_branch="main",
            local_clone_hint=str(repo),
        )
        session.add(project)
        await session.commit()
        await session.refresh(project)
        project_id = project.id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(f"/api/projects/{project_id}/introspect")

    assert res.status_code == 200
    assert res.json() == {"build": [], "test": []}
