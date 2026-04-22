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
from ouroboros_api.db.models import Base, Issue, Project, Workspace
from ouroboros_api.main import create_app
from ouroboros_api.scm.base import IssueRecord

from ._auth import install_test_admin


@pytest_asyncio.fixture
async def app_and_session(
    tmp_path: Path,
) -> AsyncIterator[tuple[object, async_sessionmaker[AsyncSession]]]:
    db_path = tmp_path / "issues-sync-reconcile.sqlite"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        ws = Workspace(slug="default", name="Default Workspace")
        session.add(ws)
        await session.flush()
        project = Project(
            workspace_id=ws.id,
            name="Demo",
            repo_url="https://github.com/acme/demo",
            scm_kind="github",
            default_branch="main",
        )
        session.add(project)
        await session.flush()
        session.add_all(
            [
                Issue(
                    workspace_id=ws.id,
                    project_id=project.id,
                    number=1,
                    title="Still open",
                    state="open",
                    labels=[],
                    assignees=[],
                ),
                Issue(
                    workspace_id=ws.id,
                    project_id=project.id,
                    number=2,
                    title="Should be closed",
                    state="open",
                    labels=[],
                    assignees=[],
                ),
            ]
        )
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


@pytest.mark.asyncio
async def test_sync_open_marks_missing_open_issues_as_closed(
    app_and_session: tuple[object, async_sessionmaker[AsyncSession]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, session_factory = app_and_session

    class FakeClient:
        async def list_issues(
            self, _repo: str, *, state: str = "open", limit: int | None = 100
        ) -> list[IssueRecord]:
            assert state == "open"
            return [
                IssueRecord(number=1, title="Still open", state="open"),
            ]

        async def get_issue(self, _repo: str, number: int) -> IssueRecord:
            return IssueRecord(number=number, title="x", state="open")

        async def comment_issue(self, _repo: str, number: int, body: str) -> None:
            return None

        async def open_pr(
            self, _repo: str, *, title: str, body: str, head: str, base: str
        ) -> str:
            return ""

        async def assign_pr_reviewer(self, _repo: str, pr_number: int, reviewer: str) -> None:
            return None

    monkeypatch.setattr("ouroboros_api.api.issues.get_client", lambda _project: FakeClient())

    async with session_factory() as session:
        project = (await session.execute(select(Project))).scalar_one()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(f"/api/projects/{project.id}/issues/sync?state=open")

    assert res.status_code == 200

    async with session_factory() as session:
        by_number = {
            issue.number: issue
            for issue in (await session.execute(select(Issue).order_by(Issue.number))).scalars()
        }
        assert by_number[1].state == "open"
        assert by_number[2].state == "closed"
