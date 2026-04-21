"""Issues router. Lists from cache; sync pulls fresh from GitHub/GitLab."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Issue, Project, Workspace
from ..db.session import SessionLocal
from ..scm import get_client
from ..scm.base import IssueRecord, repo_slug
from .deps import db_session, workspace
from .schemas import IssueOut

router = APIRouter(prefix="/api/projects/{project_id}/issues", tags=["issues"])


@dataclass
class _IssueSyncJob:
    id: str
    workspace_id: str
    project_id: str
    state: str
    status: str = "pending"
    processed: int = 0
    total: int = 0
    closed_marked: int = 0
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


_sync_jobs: dict[str, _IssueSyncJob] = {}


async def _project_or_404(
    project_id: str, ws: Workspace, session: AsyncSession
) -> Project:
    project = await session.get(Project, project_id)
    if not project or project.workspace_id != ws.id:
        raise HTTPException(404, "Project not found")
    return project


@router.get("", response_model=list[IssueOut])
async def list_issues(
    project_id: str,
    state: str = "open",
    label: str | None = None,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> list[IssueOut]:
    project = await _project_or_404(project_id, ws, session)
    stmt = select(Issue).where(Issue.project_id == project.id, Issue.state == state).order_by(Issue.number.desc())
    res = await session.execute(stmt)
    issues = list(res.scalars())
    if label:
        issues = [i for i in issues if label in (i.labels or [])]
    return [IssueOut.model_validate(i) for i in issues]


async def _apply_issue_sync(
    *,
    ws: Workspace,
    project: Project,
    session: AsyncSession,
    state: str,
    records: list[IssueRecord],
    progress: _IssueSyncJob | None = None,
) -> list[IssueOut]:
    now = datetime.now(UTC)
    fetched_numbers: set[int] = set()
    for rec in records:
        fetched_numbers.add(rec.number)
        stmt = (
            sqlite_insert(Issue)
            .values(
                workspace_id=ws.id,
                project_id=project.id,
                number=rec.number,
                title=rec.title,
                state=rec.state,
                body=rec.body,
                labels=rec.labels,
                assignees=rec.assignees,
                milestone=rec.milestone,
                url=rec.url,
                last_synced_at=now,
            )
            .on_conflict_do_update(
                index_elements=["project_id", "number"],
                set_={
                    "title": rec.title,
                    "state": rec.state,
                    "body": rec.body,
                    "labels": rec.labels,
                    "assignees": rec.assignees,
                    "milestone": rec.milestone,
                    "url": rec.url,
                    "last_synced_at": now,
                },
            )
        )
        await session.execute(stmt)
        if progress:
            progress.processed += 1

    if state == "open":
        open_issues = list(
            (
                await session.execute(
                    select(Issue).where(
                        Issue.workspace_id == ws.id,
                        Issue.project_id == project.id,
                        Issue.state == "open",
                    )
                )
            ).scalars()
        )
        for issue in open_issues:
            if issue.number in fetched_numbers:
                continue
            issue.state = "closed"
            issue.last_synced_at = now
            if progress:
                progress.closed_marked += 1

    await session.commit()
    res = await session.execute(
        select(Issue).where(Issue.project_id == project.id, Issue.state == state).order_by(Issue.number.desc())
    )
    return [IssueOut.model_validate(i) for i in res.scalars()]


@router.post("/sync", response_model=list[IssueOut])
async def sync_issues(
    project_id: str,
    state: str = "open",
    limit: int | None = None,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> list[IssueOut]:
    project = await _project_or_404(project_id, ws, session)
    client = get_client(project)
    records = await client.list_issues(repo_slug(project), state=state, limit=limit)
    return await _apply_issue_sync(
        ws=ws,
        project=project,
        session=session,
        state=state,
        records=records,
    )


async def _run_sync_job(job_id: str) -> None:
    job = _sync_jobs[job_id]
    job.started_at = datetime.now(UTC)
    try:
        async with SessionLocal() as session:
            ws = await session.get(Workspace, job.workspace_id)
            if not ws:
                raise RuntimeError("Workspace not found")
            project = await _project_or_404(job.project_id, ws, session)
            client = get_client(project)
            job.status = "fetching"
            records = await client.list_issues(repo_slug(project), state=job.state, limit=None)
            job.total = len(records)
            job.status = "applying"
            await _apply_issue_sync(
                ws=ws,
                project=project,
                session=session,
                state=job.state,
                records=records,
                progress=job,
            )
            job.status = "completed"
    except Exception as exc:  # pragma: no cover - best effort background error capture
        job.error = str(exc)
        job.status = "failed"
    finally:
        job.finished_at = datetime.now(UTC)


@router.post("/sync/start")
async def start_sync_issues(
    project_id: str,
    state: str = "open",
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> dict[str, str]:
    await _project_or_404(project_id, ws, session)
    job_id = str(uuid4())
    _sync_jobs[job_id] = _IssueSyncJob(
        id=job_id,
        workspace_id=ws.id,
        project_id=project_id,
        state=state,
    )
    asyncio.create_task(_run_sync_job(job_id))
    return {"job_id": job_id}


@router.get("/sync/{job_id}")
async def sync_issues_status(
    project_id: str,
    job_id: str,
    ws: Workspace = Depends(workspace),
) -> dict[str, str | int | None]:
    job = _sync_jobs.get(job_id)
    if not job or job.project_id != project_id or job.workspace_id != ws.id:
        raise HTTPException(404, "Sync job not found")
    return {
        "job_id": job.id,
        "status": job.status,
        "state": job.state,
        "processed": job.processed,
        "total": job.total,
        "closed_marked": job.closed_marked,
        "error": job.error,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


@router.get("/{number}", response_model=IssueOut)
async def get_issue(
    project_id: str,
    number: int,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> IssueOut:
    project = await _project_or_404(project_id, ws, session)
    res = await session.execute(
        select(Issue).where(Issue.project_id == project.id, Issue.number == number)
    )
    issue = res.scalar_one_or_none()
    if not issue:
        client = get_client(project)
        rec = await client.get_issue(repo_slug(project), number)
        issue = Issue(
            workspace_id=ws.id,
            project_id=project.id,
            number=rec.number,
            title=rec.title,
            state=rec.state,
            body=rec.body,
            labels=rec.labels,
            assignees=rec.assignees,
            milestone=rec.milestone,
            url=rec.url,
            last_synced_at=datetime.now(UTC),
        )
        session.add(issue)
        await session.commit()
        await session.refresh(issue)
    return IssueOut.model_validate(issue)
