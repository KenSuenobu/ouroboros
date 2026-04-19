"""Issues router. Lists from cache; sync pulls fresh from GitHub/GitLab."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Issue, Project, Workspace
from ..scm import get_client
from ..scm.base import repo_slug
from .deps import db_session, workspace
from .schemas import IssueOut

router = APIRouter(prefix="/api/projects/{project_id}/issues", tags=["issues"])


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


@router.post("/sync", response_model=list[IssueOut])
async def sync_issues(
    project_id: str,
    state: str = "open",
    limit: int = 100,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> list[IssueOut]:
    project = await _project_or_404(project_id, ws, session)
    client = get_client(project)
    records = await client.list_issues(repo_slug(project), state=state, limit=limit)
    now = datetime.now(UTC)
    for rec in records:
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
    await session.commit()
    res = await session.execute(
        select(Issue).where(Issue.project_id == project.id, Issue.state == state).order_by(Issue.number.desc())
    )
    return [IssueOut.model_validate(i) for i in res.scalars()]


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
