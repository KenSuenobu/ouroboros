"""Flow CRUD: react-flow JSON graphs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Flow, Workspace
from .deps import db_session, workspace
from .schemas import FlowIn, FlowOut

router = APIRouter(prefix="/api/flows", tags=["flows"])


@router.get("", response_model=list[FlowOut])
async def list_flows(
    ws: Workspace = Depends(workspace), session: AsyncSession = Depends(db_session)
) -> list[FlowOut]:
    res = await session.execute(
        select(Flow).where(Flow.workspace_id == ws.id).order_by(Flow.is_default.desc(), Flow.name)
    )
    return [FlowOut.model_validate(f) for f in res.scalars()]


@router.post("", response_model=FlowOut, status_code=201)
async def create_flow(
    payload: FlowIn,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> FlowOut:
    flow = Flow(
        workspace_id=ws.id,
        name=payload.name,
        description=payload.description,
        graph=payload.graph,
        is_default=payload.is_default,
    )
    session.add(flow)
    await session.commit()
    await session.refresh(flow)
    return FlowOut.model_validate(flow)


@router.get("/{flow_id}", response_model=FlowOut)
async def get_flow(
    flow_id: str,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> FlowOut:
    flow = await session.get(Flow, flow_id)
    if not flow or flow.workspace_id != ws.id:
        raise HTTPException(404, "Flow not found")
    return FlowOut.model_validate(flow)


@router.put("/{flow_id}", response_model=FlowOut)
async def update_flow(
    flow_id: str,
    payload: FlowIn,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> FlowOut:
    flow = await session.get(Flow, flow_id)
    if not flow or flow.workspace_id != ws.id:
        raise HTTPException(404, "Flow not found")
    flow.name = payload.name
    flow.description = payload.description
    flow.graph = payload.graph
    flow.is_default = payload.is_default
    flow.version += 1
    await session.commit()
    await session.refresh(flow)
    return FlowOut.model_validate(flow)


@router.delete("/{flow_id}", status_code=204)
async def delete_flow(
    flow_id: str,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> None:
    flow = await session.get(Flow, flow_id)
    if not flow or flow.workspace_id != ws.id:
        raise HTTPException(404, "Flow not found")
    if flow.is_default:
        raise HTTPException(400, "Cannot delete the default flow")
    await session.delete(flow)
    await session.commit()
