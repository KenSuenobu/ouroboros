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
from ouroboros_api.api import projects as projects_api
from ouroboros_api.db.models import Base, Project, Workspace
from ouroboros_api.main import create_app
from ouroboros_api.services.repo_auth import PROJECT_ACCESS_TOKEN_KEY


@pytest_asyncio.fixture
async def app_and_session(
    tmp_path: Path,
) -> AsyncIterator[tuple[object, async_sessionmaker[AsyncSession]]]:
    db_path = tmp_path / "projects-access-token.sqlite"
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
async def test_project_access_token_is_stored_but_not_exposed(
    app_and_session: tuple[object, async_sessionmaker[AsyncSession]],
) -> None:
    app, session_factory = app_and_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_res = await client.post(
            "/api/projects",
            json={
                "name": "Private Repo",
                "repo_url": "https://github.com/acme/private-repo",
                "scm_kind": "github",
                "default_branch": "main",
                "local_clone_hint": None,
                "default_flow_id": None,
                "build_command": None,
                "test_command": None,
                "config": {},
                "access_token": "secret-token-1",
            },
        )
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["has_access_token"] is True
    assert "access_token" not in created
    assert PROJECT_ACCESS_TOKEN_KEY not in created["config"]

    project_id = created["id"]
    async with session_factory() as session:
        project = await session.get(Project, project_id)
        assert project is not None
        assert project.config.get(PROJECT_ACCESS_TOKEN_KEY) == "secret-token-1"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Update without passing access_token keeps the existing token.
        update_res = await client.put(
            f"/api/projects/{project_id}",
            json={
                "name": "Private Repo Updated",
                "repo_url": "https://github.com/acme/private-repo",
                "scm_kind": "github",
                "default_branch": "main",
                "local_clone_hint": None,
                "default_flow_id": None,
                "build_command": None,
                "test_command": None,
                "config": {},
            },
        )
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["has_access_token"] is True
    assert PROJECT_ACCESS_TOKEN_KEY not in updated["config"]

    async with session_factory() as session:
        project = await session.get(Project, project_id)
        assert project is not None
        assert project.config.get(PROJECT_ACCESS_TOKEN_KEY) == "secret-token-1"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        replace_res = await client.put(
            f"/api/projects/{project_id}",
            json={
                "name": "Private Repo Updated",
                "repo_url": "https://github.com/acme/private-repo",
                "scm_kind": "github",
                "default_branch": "main",
                "local_clone_hint": None,
                "default_flow_id": None,
                "build_command": None,
                "test_command": None,
                "config": {},
                "access_token": "secret-token-2",
            },
        )
    assert replace_res.status_code == 200
    replaced = replace_res.json()
    assert replaced["has_access_token"] is True

    async with session_factory() as session:
        project = await session.get(Project, project_id)
        assert project is not None
        assert project.config.get(PROJECT_ACCESS_TOKEN_KEY) == "secret-token-2"

        listed = list((await session.execute(select(Project))).scalars())
        assert len(listed) == 1


@pytest.mark.asyncio
async def test_project_repo_test_endpoint_reports_success_and_failure(
    app_and_session: tuple[object, async_sessionmaker[AsyncSession]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, session_factory = app_and_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_res = await client.post(
            "/api/projects",
            json={
                "name": "Repo Probe",
                "repo_url": "https://github.com/acme/private-repo",
                "scm_kind": "github",
                "default_branch": "main",
                "local_clone_hint": None,
                "default_flow_id": None,
                "build_command": None,
                "test_command": None,
                "config": {},
            },
        )
    assert create_res.status_code == 201
    project_id = create_res.json()["id"]

    monkeypatch.setattr(
        projects_api,
        "_test_repo_access",
        lambda _project: (True, "Repository is reachable and credentials are valid."),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ok_res = await client.post(f"/api/projects/{project_id}/test-repo")
    assert ok_res.status_code == 200
    assert ok_res.json() == {
        "ok": True,
        "message": "Repository is reachable and credentials are valid.",
    }

    monkeypatch.setattr(
        projects_api,
        "_test_repo_access",
        lambda _project: (False, "Repository access denied."),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        fail_res = await client.post(f"/api/projects/{project_id}/test-repo")
    assert fail_res.status_code == 200
    assert fail_res.json() == {
        "ok": False,
        "message": "Repository access denied.",
    }


@pytest.mark.asyncio
async def test_project_repo_test_draft_endpoint_uses_payload_values(
    app_and_session: tuple[object, async_sessionmaker[AsyncSession]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, _ = app_and_session

    captured: dict[str, str | None] = {}

    def fake_test(repo_url: str, default_branch: str, access_token: str | None) -> tuple[bool, str]:
        captured["repo_url"] = repo_url
        captured["default_branch"] = default_branch
        captured["access_token"] = access_token
        return True, "ok"

    monkeypatch.setattr(projects_api, "_test_repo_access_values", fake_test)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/projects/test-repo",
            json={
                "repo_url": "https://github.com/acme/private-repo",
                "default_branch": "develop",
                "access_token": "abc123",
            },
        )
    assert res.status_code == 200
    assert res.json() == {"ok": True, "message": "ok"}
    assert captured == {
        "repo_url": "https://github.com/acme/private-repo",
        "default_branch": "develop",
        "access_token": "abc123",
    }
