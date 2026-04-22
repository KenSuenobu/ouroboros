"""Common API dependencies: DB session, current user, workspace, membership."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.models import User, Workspace, WorkspaceMembership
from ..db.session import SessionLocal
from ..services import auth as auth_svc


async def db_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization") or ""
    if header.lower().startswith("bearer "):
        return header.split(" ", 1)[1].strip() or None
    return None


async def optional_current_user(
    request: Request, session: AsyncSession = Depends(db_session)
) -> User | None:
    token = request.cookies.get(settings.auth_session_cookie_name) or _bearer_token(request)
    if not token:
        return None
    resolved = await auth_svc.resolve_session(session, token)
    if not resolved:
        return None
    _, user = resolved
    await session.commit()
    return user


async def current_user(
    request: Request, session: AsyncSession = Depends(db_session)
) -> User:
    token = request.cookies.get(settings.auth_session_cookie_name) or _bearer_token(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")
    resolved = await auth_svc.resolve_session(session, token)
    if not resolved:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")
    _, user = resolved
    await session.commit()
    return user


async def workspace(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
) -> Workspace:
    """Resolve workspace from header/query, then assert the caller is a member."""
    slug = (
        request.headers.get("x-workspace")
        or request.query_params.get("workspace")
        or settings.default_workspace_slug
    )
    ws = (
        await session.execute(select(Workspace).where(Workspace.slug == slug))
    ).scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail=f"Workspace {slug!r} not found")

    membership = (
        await session.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == ws.id,
                WorkspaceMembership.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=403, detail="not a member of this workspace")
    return ws


async def current_membership(
    user: User = Depends(current_user),
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> WorkspaceMembership:
    membership = (
        await session.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == ws.id,
                WorkspaceMembership.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=403, detail="not a member of this workspace")
    return membership


async def require_admin(
    membership: WorkspaceMembership = Depends(current_membership),
) -> WorkspaceMembership:
    if membership.role != "admin":
        raise HTTPException(status_code=403, detail="administrator role required")
    return membership
