"""Workspace router (list-only in local mode; auth/CRUD added in hosted mode)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Workspace
from .deps import db_session
from .schemas import WorkspaceOut

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


@router.get("", response_model=list[WorkspaceOut])
async def list_workspaces(session: AsyncSession = Depends(db_session)) -> list[WorkspaceOut]:
    res = await session.execute(select(Workspace).order_by(Workspace.created_at))
    return [WorkspaceOut.model_validate(w) for w in res.scalars()]
