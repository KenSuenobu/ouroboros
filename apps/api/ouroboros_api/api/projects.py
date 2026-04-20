"""Project CRUD."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Project, Workspace
from ..services.repo_introspect import introspect_project_commands, repo_introspector
from .deps import db_session, workspace
from .schemas import ProjectIn, ProjectIntrospectionOut, ProjectOut

router = APIRouter(prefix="/api/projects", tags=["projects"])


async def _project_or_404(project_id: str, ws: Workspace, session: AsyncSession) -> Project:
    project = await session.get(Project, project_id)
    if not project or project.workspace_id != ws.id:
        raise HTTPException(404, "Project not found")
    return project


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    ws: Workspace = Depends(workspace), session: AsyncSession = Depends(db_session)
) -> list[ProjectOut]:
    res = await session.execute(
        select(Project).where(Project.workspace_id == ws.id).order_by(Project.created_at)
    )
    return [ProjectOut.model_validate(p) for p in res.scalars()]


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(
    payload: ProjectIn,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> ProjectOut:
    project = Project(workspace_id=ws.id, **payload.model_dump())
    session.add(project)
    await session.commit()
    await session.refresh(project)
    repo_introspector.invalidate(project.id)
    return ProjectOut.model_validate(project)


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: str,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> ProjectOut:
    project = await _project_or_404(project_id, ws, session)
    return ProjectOut.model_validate(project)


@router.put("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: str,
    payload: ProjectIn,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> ProjectOut:
    project = await _project_or_404(project_id, ws, session)
    repo_introspector.invalidate(project.id)
    for key, value in payload.model_dump().items():
        setattr(project, key, value)
    await session.commit()
    await session.refresh(project)
    return ProjectOut.model_validate(project)


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: str,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> None:
    project = await _project_or_404(project_id, ws, session)
    repo_introspector.invalidate(project.id)
    await session.delete(project)
    await session.commit()


@router.get("/{project_id}/introspect", response_model=ProjectIntrospectionOut)
async def introspect_project(
    project_id: str,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> ProjectIntrospectionOut:
    project = await _project_or_404(project_id, ws, session)
    suggestions = introspect_project_commands(project)
    return ProjectIntrospectionOut(**suggestions.as_dict())
