"""Workspace router (list-only in local mode; auth/CRUD added in hosted mode)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Project, Provider, User, Workspace, WorkspaceMembership
from .deps import current_user, db_session, require_admin, workspace
from .schemas import WorkspaceMeOut, WorkspaceOnboardingIn, WorkspaceOut

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


async def _workspace_status(session: AsyncSession, ws: Workspace) -> WorkspaceMeOut:
    project_count = await session.scalar(
        select(func.count(Project.id)).where(Project.workspace_id == ws.id)
    )
    provider_count = await session.scalar(
        select(func.count(Provider.id)).where(Provider.workspace_id == ws.id)
    )
    project_count = int(project_count or 0)
    provider_count = int(provider_count or 0)
    requires_onboarding = (
        ws.onboarding_completed_at is None and (project_count == 0 or provider_count == 0)
    )
    return WorkspaceMeOut(
        id=ws.id,
        slug=ws.slug,
        name=ws.name,
        onboarding_completed_at=ws.onboarding_completed_at,
        project_count=project_count,
        provider_count=provider_count,
        requires_onboarding=requires_onboarding,
    )


@router.get("", response_model=list[WorkspaceOut])
async def list_workspaces(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
) -> list[WorkspaceOut]:
    res = await session.execute(
        select(Workspace)
        .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
        .where(WorkspaceMembership.user_id == user.id)
        .order_by(Workspace.created_at)
    )
    return [WorkspaceOut.model_validate(w) for w in res.scalars()]


@router.get("/me", response_model=WorkspaceMeOut)
async def get_workspace_me(
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> WorkspaceMeOut:
    return await _workspace_status(session, ws)


@router.post(
    "/me/onboarding", response_model=WorkspaceMeOut, dependencies=[Depends(require_admin)]
)
async def complete_onboarding(
    payload: WorkspaceOnboardingIn,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> WorkspaceMeOut:
    name = payload.name.strip() if payload.name else ""
    if name:
        ws.name = name
    ws.onboarding_completed_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(ws)
    return await _workspace_status(session, ws)
