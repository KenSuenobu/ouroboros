"""Common API dependencies: workspace context, DB session."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.models import Workspace
from ..db.session import SessionLocal


async def db_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def workspace(
    request: Request, session: AsyncSession = Depends(db_session)
) -> Workspace:
    """Resolve workspace from header, query, or fall back to the default."""
    slug = (
        request.headers.get("x-workspace")
        or request.query_params.get("workspace")
        or settings.default_workspace_slug
    )
    res = await session.execute(select(Workspace).where(Workspace.slug == slug))
    ws = res.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail=f"Workspace {slug!r} not found")
    return ws
