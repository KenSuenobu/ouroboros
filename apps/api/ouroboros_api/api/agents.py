"""Agent CRUD + tool bindings + dry-run test."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..adapters.base import ResolvedModel
from ..adapters.registry import adapters
from ..config import settings
from ..db.models import (
    Agent,
    AgentToolBinding,
    Provider,
    ProviderModel,
    Workspace,
)
from ..orchestrator.context import RunContext
from ..orchestrator.router import pick_model
from ..sandbox import VirtualFs
from ..secrets import secrets
from .deps import db_session, workspace
from .schemas import (
    AgentIn,
    AgentOut,
    AgentTestRequest,
    AgentTestResponse,
    AgentToolBindingIn,
)

router = APIRouter(prefix="/api/agents", tags=["agents"])


async def _to_out(session: AsyncSession, agent: Agent) -> AgentOut:
    bindings = list(
        (await session.execute(select(AgentToolBinding).where(AgentToolBinding.agent_id == agent.id))).scalars()
    )
    return AgentOut(
        id=agent.id,
        workspace_id=agent.workspace_id,
        name=agent.name,
        role=agent.role,
        description=agent.description,
        system_prompt=agent.system_prompt,
        execution_adapter=agent.execution_adapter,
        model_policy=agent.model_policy,
        config=agent.config,
        dry_run_default=agent.dry_run_default,
        is_builtin=agent.is_builtin,
        tool_bindings=[
            AgentToolBindingIn(tool_kind=b.tool_kind, tool_ref=b.tool_ref, config=b.config) for b in bindings
        ],
    )


@router.get("", response_model=list[AgentOut])
async def list_agents(
    ws: Workspace = Depends(workspace), session: AsyncSession = Depends(db_session)
) -> list[AgentOut]:
    res = await session.execute(
        select(Agent).where(Agent.workspace_id == ws.id).order_by(Agent.role)
    )
    return [await _to_out(session, a) for a in res.scalars()]


@router.post("", response_model=AgentOut, status_code=201)
async def create_agent(
    payload: AgentIn,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> AgentOut:
    if payload.execution_adapter not in adapters().names():
        raise HTTPException(400, f"Unknown adapter: {payload.execution_adapter}")
    agent = Agent(
        workspace_id=ws.id,
        name=payload.name,
        role=payload.role,
        description=payload.description,
        system_prompt=payload.system_prompt,
        execution_adapter=payload.execution_adapter,
        model_policy=payload.model_policy.model_dump(),
        config=payload.config,
        dry_run_default=payload.dry_run_default,
    )
    session.add(agent)
    await session.flush()
    for b in payload.tool_bindings:
        session.add(
            AgentToolBinding(
                workspace_id=ws.id, agent_id=agent.id, tool_kind=b.tool_kind, tool_ref=b.tool_ref, config=b.config
            )
        )
    await session.commit()
    await session.refresh(agent)
    return await _to_out(session, agent)


@router.put("/{agent_id}", response_model=AgentOut)
async def update_agent(
    agent_id: str,
    payload: AgentIn,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> AgentOut:
    agent = await session.get(Agent, agent_id)
    if not agent or agent.workspace_id != ws.id:
        raise HTTPException(404, "Agent not found")
    if payload.execution_adapter not in adapters().names():
        raise HTTPException(400, f"Unknown adapter: {payload.execution_adapter}")
    agent.name = payload.name
    agent.role = payload.role
    agent.description = payload.description
    agent.system_prompt = payload.system_prompt
    agent.execution_adapter = payload.execution_adapter
    agent.model_policy = payload.model_policy.model_dump()
    agent.config = payload.config
    agent.dry_run_default = payload.dry_run_default
    await session.execute(delete(AgentToolBinding).where(AgentToolBinding.agent_id == agent.id))
    for b in payload.tool_bindings:
        session.add(
            AgentToolBinding(
                workspace_id=ws.id, agent_id=agent.id, tool_kind=b.tool_kind, tool_ref=b.tool_ref, config=b.config
            )
        )
    await session.commit()
    await session.refresh(agent)
    return await _to_out(session, agent)


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: str,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> None:
    agent = await session.get(Agent, agent_id)
    if not agent or agent.workspace_id != ws.id:
        raise HTTPException(404, "Agent not found")
    if agent.is_builtin:
        raise HTTPException(400, "Built-in agents cannot be deleted")
    await session.delete(agent)
    await session.commit()


@router.get("/_meta/adapters")
async def adapter_names() -> dict[str, list[str]]:
    return {"adapters": adapters().names()}


@router.post("/{agent_id}/test", response_model=AgentTestResponse)
async def test_agent(
    agent_id: str,
    payload: AgentTestRequest,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> AgentTestResponse:
    agent = await session.get(Agent, agent_id)
    if not agent or agent.workspace_id != ws.id:
        raise HTTPException(404, "Agent not found")

    providers_list = list(
        (await session.execute(select(Provider).where(Provider.workspace_id == ws.id))).scalars()
    )
    models_by_provider: dict[str, list[ProviderModel]] = {}
    for p in providers_list:
        res = await session.execute(select(ProviderModel).where(ProviderModel.provider_id == p.id))
        models_by_provider[p.id] = list(res.scalars())

    overrides = {}
    if payload.provider_override_id and payload.model_override_id:
        overrides[agent.role] = {
            "provider_id": payload.provider_override_id,
            "model_id": payload.model_override_id,
        }

    chosen = pick_model(agent, providers_list, models_by_provider, None, overrides)
    if chosen is None and agent.execution_adapter not in {"builtin", "opencode_cli", "gh_copilot_cli"}:
        raise HTTPException(400, "No usable provider configured for this agent")

    provider = chosen[0] if chosen else None
    model = chosen[1] if chosen else None
    resolved = ResolvedModel(
        provider_id=provider.id if provider else "",
        provider_kind=provider.kind if provider else "",
        model_id=model.model_id if model else "",
        base_url=provider.base_url if provider else None,
        api_key=secrets.get(provider.api_key_secret_ref) if provider and provider.api_key_secret_ref else None,
        extra=dict(provider.config or {}) if provider else {},
    )

    sandbox_dir = settings.data_dir / "agent-tests" / str(uuid.uuid4())
    sandbox_dir.mkdir(parents=True, exist_ok=True)

    ctx = RunContext(
        workspace_id=ws.id,
        project_id="(none)",
        run_id=f"agent-test:{agent.id}",
        sandbox_path=sandbox_dir,
        vfs=VirtualFs(sandbox_dir),
        dry_run=payload.dry_run,
    )
    ctx.scratchpad["agent_input"] = payload.input_text

    try:
        adapter = adapters().get(agent.execution_adapter)
    except KeyError as exc:
        raise HTTPException(400, str(exc)) from exc

    try:
        result = await adapter.run(ctx, agent, resolved)
    finally:
        try:
            import shutil

            shutil.rmtree(sandbox_dir, ignore_errors=True)
        except Exception:
            pass

    return AgentTestResponse(
        output=result.summary,
        model_used=resolved.model_id or "(none)",
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        artifacts=result.artifacts,
        warnings=result.warnings,
    )
