"""Roadmap router: parse FUTURE/PLANNED roadmap markdown files in the project's clone."""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.models import IssueRoadmapPair, Project, RoadmapEntry, Workspace
from ..services.roadmap_parser import discover_roadmap_files, parse_roadmap_file
from .deps import db_session, workspace
from .schemas import IssueRoadmapPairIn, IssueRoadmapPairOut, RoadmapEntryOut

router = APIRouter(prefix="/api/projects/{project_id}/roadmap", tags=["roadmap"])


async def _project_or_404(project_id: str, ws: Workspace, session: AsyncSession) -> Project:
    project = await session.get(Project, project_id)
    if not project or project.workspace_id != ws.id:
        raise HTTPException(404, "Project not found")
    return project


def _resolve_repo_root(project: Project) -> Path | None:
    if project.local_clone_hint:
        candidate = Path(project.local_clone_hint).expanduser()
        if candidate.exists():
            return candidate
    cached = settings.data_dir / "roadmap-cache" / project.id
    if cached.exists():
        return cached
    return None


def _shallow_clone(project: Project) -> Path:
    target = settings.data_dir / "roadmap-cache" / project.id
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        shutil.rmtree(target)
    import subprocess

    subprocess.run(
        ["git", "clone", "--depth", "1", project.repo_url, str(target)],
        check=True,
        capture_output=True,
    )
    return target


@router.get("", response_model=list[RoadmapEntryOut])
async def list_entries(
    project_id: str,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> list[RoadmapEntryOut]:
    project = await _project_or_404(project_id, ws, session)
    res = await session.execute(
        select(RoadmapEntry).where(RoadmapEntry.project_id == project.id).order_by(RoadmapEntry.kind, RoadmapEntry.title)
    )
    return [RoadmapEntryOut.model_validate(e) for e in res.scalars()]


@router.post("/sync", response_model=list[RoadmapEntryOut])
async def sync_roadmap(
    project_id: str,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> list[RoadmapEntryOut]:
    project = await _project_or_404(project_id, ws, session)
    root = _resolve_repo_root(project)
    if not root:
        try:
            root = _shallow_clone(project)
        except Exception as exc:
            raise HTTPException(400, f"Could not clone {project.repo_url!r}: {exc}") from exc

    await session.execute(delete(RoadmapEntry).where(RoadmapEntry.project_id == project.id))
    files = discover_roadmap_files(root)
    for f in files:
        for parsed in parse_roadmap_file(f):
            session.add(
                RoadmapEntry(
                    workspace_id=ws.id,
                    project_id=project.id,
                    file_path=str(f.relative_to(root)),
                    section=parsed.section,
                    title=parsed.title,
                    body=parsed.body,
                    status=parsed.status,
                    kind=parsed.kind,
                )
            )
    await session.commit()
    res = await session.execute(
        select(RoadmapEntry).where(RoadmapEntry.project_id == project.id).order_by(RoadmapEntry.kind, RoadmapEntry.title)
    )
    return [RoadmapEntryOut.model_validate(e) for e in res.scalars()]


@router.post("/pairs", response_model=IssueRoadmapPairOut, status_code=201)
async def create_pair(
    project_id: str,
    payload: IssueRoadmapPairIn,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> IssueRoadmapPairOut:
    await _project_or_404(project_id, ws, session)
    pair = IssueRoadmapPair(workspace_id=ws.id, **payload.model_dump())
    session.add(pair)
    await session.commit()
    await session.refresh(pair)
    return IssueRoadmapPairOut.model_validate(pair)


@router.delete("/pairs/{pair_id}", status_code=204)
async def delete_pair(
    project_id: str,
    pair_id: str,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> None:
    await _project_or_404(project_id, ws, session)
    pair = await session.get(IssueRoadmapPair, pair_id)
    if not pair or pair.workspace_id != ws.id:
        raise HTTPException(404, "Pair not found")
    await session.delete(pair)
    await session.commit()


@router.get("/pairs", response_model=list[IssueRoadmapPairOut])
async def list_pairs(
    project_id: str,
    issue_id: str | None = None,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> list[IssueRoadmapPairOut]:
    await _project_or_404(project_id, ws, session)
    stmt = select(IssueRoadmapPair).where(IssueRoadmapPair.workspace_id == ws.id)
    if issue_id:
        stmt = stmt.where(IssueRoadmapPair.issue_id == issue_id)
    res = await session.execute(stmt)
    return [IssueRoadmapPairOut.model_validate(p) for p in res.scalars()]
