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
from ouroboros_api.db.models import (
    Base,
    Flow,
    Intervention,
    Project,
    Run,
    RunArtifact,
    RunStep,
    Workspace,
)
from ouroboros_api.main import create_app

from ._auth import install_test_admin


@pytest_asyncio.fixture
async def app_and_session(
    tmp_path: Path,
) -> AsyncIterator[tuple[object, async_sessionmaker[AsyncSession]]]:
    db_path = tmp_path / "runs-delete.sqlite"
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


async def _seed_run_with_history(session: AsyncSession) -> tuple[Run, RunStep]:
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
        title="Delete me",
        status="succeeded",
        dry_run=True,
    )
    session.add(run)
    await session.flush()

    step = RunStep(
        workspace_id=ws.id,
        run_id=run.id,
        node_id="plan",
        sequence=1,
        attempt=1,
        status="succeeded",
        dry_run=True,
    )
    session.add(step)
    await session.flush()

    session.add(
        RunArtifact(
            workspace_id=ws.id,
            run_step_id=step.id,
            kind="log",
            name="stdout",
            inline_content="ok",
        )
    )
    session.add(
        Intervention(
            workspace_id=ws.id,
            run_id=run.id,
            run_step_id=step.id,
            kind="question",
            prompt="continue?",
            options=[],
            status="answered",
        )
    )
    await session.commit()
    await session.refresh(run)
    await session.refresh(step)
    return run, step


@pytest.mark.asyncio
async def test_delete_run_removes_run_and_history(
    app_and_session: tuple[object, async_sessionmaker[AsyncSession]],
) -> None:
    app, session_factory = app_and_session
    async with session_factory() as session:
        run, step = await _seed_run_with_history(session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.delete(f"/api/runs/{run.id}")

    assert res.status_code == 204

    async with session_factory() as session:
        assert await session.get(Run, run.id) is None
        assert await session.get(RunStep, step.id) is None
        artifacts = list(
            (await session.execute(select(RunArtifact).where(RunArtifact.run_step_id == step.id))).scalars()
        )
        interventions = list(
            (await session.execute(select(Intervention).where(Intervention.run_id == run.id))).scalars()
        )
        assert artifacts == []
        assert interventions == []


@pytest.mark.asyncio
async def test_delete_run_rejects_active_run(
    app_and_session: tuple[object, async_sessionmaker[AsyncSession]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, session_factory = app_and_session
    async with session_factory() as session:
        run, _ = await _seed_run_with_history(session)

    monkeypatch.setattr("ouroboros_api.api.runs.run_manager.is_running", lambda _run_id: True)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.delete(f"/api/runs/{run.id}")

    assert res.status_code == 409
    assert "currently active" in res.text
