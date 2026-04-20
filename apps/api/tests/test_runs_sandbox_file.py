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
from ouroboros_api.db.models import Base, Flow, Project, Run, Workspace
from ouroboros_api.main import create_app


@pytest_asyncio.fixture
async def app_and_session(
    tmp_path: Path,
) -> AsyncIterator[tuple[object, async_sessionmaker[AsyncSession], Path]]:
    db_path = tmp_path / "runs-sandbox-file.sqlite"
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
        yield app, session_factory, tmp_path
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


async def _seed_run(session: AsyncSession, sandbox_path: Path) -> Run:
    ws = (await session.execute(select(Workspace).where(Workspace.slug == "default"))).scalar_one()
    project = Project(
        workspace_id=ws.id,
        name="Demo",
        repo_url="https://github.com/acme/demo",
        scm_kind="github",
        default_branch="main",
    )
    flow = Flow(
        workspace_id=ws.id,
        name="Flow",
        graph={"nodes": [], "edges": []},
        is_default=True,
    )
    session.add_all([project, flow])
    await session.flush()
    run = Run(
        workspace_id=ws.id,
        project_id=project.id,
        flow_id=flow.id,
        title="Diff run",
        status="succeeded",
        dry_run=True,
        sandbox_path=str(sandbox_path),
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


@pytest.mark.asyncio
async def test_sandbox_file_returns_file_content(
    app_and_session: tuple[object, async_sessionmaker[AsyncSession], Path],
) -> None:
    app, session_factory, tmp_path = app_and_session
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    target = sandbox / "src" / "app.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("print('hello')\n", encoding="utf-8")

    async with session_factory() as session:
        run = await _seed_run(session, sandbox)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(f"/api/runs/{run.id}/sandbox-file", params={"path": "src/app.py"})

    assert res.status_code == 200
    payload = res.json()
    assert payload["path"] == "src/app.py"
    assert payload["content"] == "print('hello')\n"


@pytest.mark.asyncio
async def test_sandbox_file_rejects_path_traversal(
    app_and_session: tuple[object, async_sessionmaker[AsyncSession], Path],
) -> None:
    app, session_factory, tmp_path = app_and_session
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    (sandbox / "README.md").write_text("ok\n", encoding="utf-8")

    async with session_factory() as session:
        run = await _seed_run(session, sandbox)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(f"/api/runs/{run.id}/sandbox-file", params={"path": "../../etc/passwd"})

    assert res.status_code == 400
    assert "escapes sandbox" in res.text
