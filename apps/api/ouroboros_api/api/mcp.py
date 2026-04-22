"""MCP router: registry browse, install/list/test installed servers, invoke tools."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import McpServer, Workspace
from ..mcp import McpManager, RegistryClient
from .deps import current_user, db_session, require_admin, workspace
from .schemas import McpInstallRequest, McpRegistryEntry, McpServerOut, McpToolInvokeRequest

router = APIRouter(prefix="/api/mcp", tags=["mcp"])
_registry = RegistryClient()


@router.get(
    "/registry", response_model=list[McpRegistryEntry], dependencies=[Depends(current_user)]
)
async def browse_registry(q: str | None = None, limit: int = 100) -> list[McpRegistryEntry]:
    items = await _registry.list_servers(q=q, limit=limit)
    return [McpRegistryEntry(**i) for i in items]


@router.get(
    "/registry/{server_id}",
    response_model=McpRegistryEntry,
    dependencies=[Depends(current_user)],
)
async def get_registry_entry(server_id: str) -> McpRegistryEntry:
    item = await _registry.get_server(server_id)
    if not item:
        raise HTTPException(404, "Server not found")
    return McpRegistryEntry(**item)


@router.get("/servers", response_model=list[McpServerOut])
async def list_servers(
    ws: Workspace = Depends(workspace), session: AsyncSession = Depends(db_session)
) -> list[McpServerOut]:
    res = await session.execute(
        select(McpServer).where(McpServer.workspace_id == ws.id).order_by(McpServer.name)
    )
    return [McpServerOut.model_validate(s) for s in res.scalars()]


@router.post(
    "/servers",
    response_model=McpServerOut,
    status_code=201,
    dependencies=[Depends(require_admin)],
)
async def install_server(
    payload: McpInstallRequest,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> McpServerOut:
    server = McpServer(
        workspace_id=ws.id,
        name=payload.name,
        registry_id=payload.registry_id,
        transport=payload.transport,
        install_spec=payload.install_spec,
        config=payload.config,
        side_effecting=payload.side_effecting,
        status="installed",
    )
    session.add(server)
    await session.commit()
    await session.refresh(server)
    return McpServerOut.model_validate(server)


@router.delete("/servers/{server_id}", status_code=204, dependencies=[Depends(require_admin)])
async def delete_server(
    server_id: str,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> None:
    server = await session.get(McpServer, server_id)
    if not server or server.workspace_id != ws.id:
        raise HTTPException(404, "Server not found")
    await session.delete(server)
    await session.commit()


@router.get("/servers/{server_id}/tools")
async def list_tools(
    server_id: str,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> dict:
    server = await session.get(McpServer, server_id)
    if not server or server.workspace_id != ws.id:
        raise HTTPException(404, "Server not found")
    mgr = McpManager()
    info = await mgr.open([server])
    tools = info[server.name].tools
    error = info[server.name].error
    await mgr.close()
    return {"tools": tools, "error": error}


@router.post("/servers/{server_id}/invoke", dependencies=[Depends(require_admin)])
async def invoke_tool(
    server_id: str,
    payload: McpToolInvokeRequest,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> dict:
    server = await session.get(McpServer, server_id)
    if not server or server.workspace_id != ws.id:
        raise HTTPException(404, "Server not found")
    mgr = McpManager()
    await mgr.open([server])
    result = await mgr.call(server.name, payload.tool, payload.arguments)
    await mgr.close()
    return result
