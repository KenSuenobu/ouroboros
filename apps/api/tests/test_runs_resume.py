from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ouroboros_api.api import deps
from ouroboros_api.db.models import Base, Flow, Project, Run, RunStep, Workspace
from ouroboros_api.main import create_app
from ouroboros_api.orchestrator.engine import RunEngine, interrupt_in_flight_runs


@pytest_asyncio.fixture
async def app_and_session(
    tmp_path: Path,
) -> AsyncIterator[tuple[object, async_sessionmaker[AsyncSession]]]:
    db_path = tmp_path / "runs-resume.sqlite"
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


async def _seed_run(
    session: AsyncSession,
    *,
    status: str,
    graph: dict | None = None,
    snapshot_json: dict | None = None,
) -> Run:
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
        graph=graph
        or {
            "nodes": [{"id": "a", "type": "noop"}, {"id": "b", "type": "noop"}, {"id": "c", "type": "noop"}],
            "edges": [{"source": "a", "target": "b"}, {"source": "b", "target": "c"}],
        },
        is_default=True,
    )
    session.add_all([project, flow])
    await session.flush()
    run = Run(
        workspace_id=ws.id,
        project_id=project.id,
        flow_id=flow.id,
        title="Resume run",
        status=status,
        dry_run=True,
        snapshot_json=snapshot_json or {},
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


@pytest.mark.asyncio
async def test_resume_endpoint_starts_resume_task_for_interrupted_run(
    app_and_session: tuple[object, async_sessionmaker[AsyncSession]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, session_factory = app_and_session
    async with session_factory() as session:
        run = await _seed_run(session, status="interrupted")

    called: list[str] = []

    async def fake_resume(run_id: str) -> None:
        called.append(run_id)

    monkeypatch.setattr("ouroboros_api.api.runs.run_manager.resume", fake_resume)
    monkeypatch.setattr("ouroboros_api.api.runs.run_manager.is_running", lambda _run_id: False)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(f"/api/runs/{run.id}/resume")

    assert res.status_code == 200
    assert called == [run.id]


@pytest.mark.asyncio
async def test_resume_endpoint_rejects_non_interrupted_run(
    app_and_session: tuple[object, async_sessionmaker[AsyncSession]],
) -> None:
    app, session_factory = app_and_session
    async with session_factory() as session:
        run = await _seed_run(session, status="failed")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(f"/api/runs/{run.id}/resume")

    assert res.status_code == 400
    assert "interrupted" in res.text


@pytest.mark.asyncio
async def test_interrupt_in_flight_runs_marks_runs_and_steps_interrupted(
    app_and_session: tuple[object, async_sessionmaker[AsyncSession]],
) -> None:
    _, session_factory = app_and_session
    async with session_factory() as session:
        run = await _seed_run(session, status="running")
        session.add(
            RunStep(
                workspace_id=run.workspace_id,
                run_id=run.id,
                node_id="a",
                sequence=1,
                attempt=1,
                status="running",
                dry_run=True,
            )
        )
        await session.commit()
        count = await interrupt_in_flight_runs(session)
        assert count == 1

    async with session_factory() as session:
        updated_run = await session.get(Run, run.id)
        assert updated_run is not None
        assert updated_run.status == "interrupted"
        updated_step = (
            await session.execute(select(RunStep).where(RunStep.run_id == run.id))
        ).scalar_one()
        assert updated_step.status == "interrupted"


@pytest.mark.asyncio
async def test_engine_resume_skips_previously_succeeded_nodes(
    app_and_session: tuple[object, async_sessionmaker[AsyncSession]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _, session_factory = app_and_session
    async with session_factory() as session:
        run = await _seed_run(
            session,
            status="interrupted",
            snapshot_json={"scratchpad": {"branch": "ticket-13"}, "issue": {"number": 13}},
        )
        session.add(
            RunStep(
                workspace_id=run.workspace_id,
                run_id=run.id,
                node_id="a",
                sequence=1,
                attempt=1,
                status="succeeded",
                dry_run=True,
            )
        )
        await session.commit()

    async def fake_prepare_sandbox(_run_id: str, _repo_url: str, _default_branch: str) -> SimpleNamespace:
        return SimpleNamespace(repo_path=tmp_path)

    monkeypatch.setattr("ouroboros_api.orchestrator.engine.prepare_sandbox", fake_prepare_sandbox)
    monkeypatch.setattr("ouroboros_api.orchestrator.engine.SessionLocal", session_factory)

    engine = RunEngine()
    await engine._execute(run.id, resume=True)

    async with session_factory() as session:
        steps = list(
            (
                await session.execute(select(RunStep).where(RunStep.run_id == run.id).order_by(RunStep.sequence))
            ).scalars()
        )
        assert [s.node_id for s in steps] == ["a", "b", "c"]
        assert [s.status for s in steps] == ["succeeded", "succeeded", "succeeded"]
        updated_run = await session.get(Run, run.id)
        assert updated_run is not None
        assert updated_run.status == "succeeded"
        assert updated_run.snapshot_json.get("scratchpad", {}).get("branch") == "ticket-13"
