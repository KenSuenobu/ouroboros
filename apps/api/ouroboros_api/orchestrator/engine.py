"""Run engine: walks the flow graph node-by-node, dispatching to adapters."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..adapters.base import ResolvedModel, StepResult
from ..adapters.registry import adapters
from ..db.models import (
    Agent,
    Flow,
    Intervention,
    Project,
    Provider,
    ProviderModel,
    Run,
    RunArtifact,
    RunStep,
)
from ..db.session import SessionLocal
from ..sandbox import VirtualFs, prepare_sandbox, shell_line_subscriber
from ..secrets import secrets
from .context import RunContext
from .cost import estimate_cost_usd
from .dry_run import is_dry_run, step_is_side_effecting
from .events import RunEvent, bus
from .intervention import registry as intervention_registry
from .router import pick_model

log = logging.getLogger("ouroboros.engine")

MAX_STEP_RETRIES = 3


class RunEngine:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[Any]] = {}

    def is_running(self, run_id: str) -> bool:
        task = self._tasks.get(run_id)
        return bool(task) and not task.done()

    async def start(self, run_id: str) -> None:
        if self.is_running(run_id):
            return
        task = asyncio.create_task(self._safe_execute(run_id), name=f"run:{run_id}")
        self._tasks[run_id] = task

    async def cancel(self, run_id: str) -> bool:
        task = self._tasks.get(run_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    async def _safe_execute(self, run_id: str) -> None:
        try:
            await self._execute(run_id)
        except Exception as exc:
            log.exception("run %s failed at top level", run_id)
            await bus.publish(RunEvent(run_id=run_id, type="run.failed", payload={"error": str(exc)}))
            async with SessionLocal() as session:
                run = await session.get(Run, run_id)
                if run:
                    run.status = "failed"
                    run.error = str(exc)
                    run.finished_at = datetime.now(UTC)
                    await session.commit()

    async def _execute(self, run_id: str) -> None:
        async with SessionLocal() as session:
            run = await session.get(Run, run_id)
            if not run:
                return
            project = await session.get(Project, run.project_id)
            flow = await session.get(Flow, run.flow_id)
            if not project or not flow:
                run.status = "failed"
                run.error = "missing project or flow"
                await session.commit()
                return

            providers_list = list(
                (await session.execute(select(Provider).where(Provider.workspace_id == run.workspace_id))).scalars()
            )
            models_by_provider: dict[str, list[ProviderModel]] = {}
            for p in providers_list:
                res = await session.execute(
                    select(ProviderModel).where(ProviderModel.provider_id == p.id)
                )
                models_by_provider[p.id] = list(res.scalars())
            agents_list = list(
                (await session.execute(select(Agent).where(Agent.workspace_id == run.workspace_id))).scalars()
            )
            agents_by_role = {a.role: a for a in agents_list}

            run.status = "running"
            run.started_at = datetime.now(UTC)
            await session.commit()

            await bus.publish(RunEvent(run_id=run.id, type="run.started", payload={"dry_run": run.dry_run}))

            try:
                sandbox = await prepare_sandbox(run.id, project.repo_url, project.default_branch)
            except Exception as exc:
                run.status = "failed"
                run.error = f"sandbox setup: {exc}"
                run.finished_at = datetime.now(UTC)
                await session.commit()
                await bus.publish(RunEvent(run_id=run.id, type="run.failed", payload={"error": run.error}))
                return
            run.sandbox_path = str(sandbox.repo_path)
            await session.commit()

            ctx = RunContext(
                workspace_id=run.workspace_id,
                project_id=run.project_id,
                run_id=run.id,
                sandbox_path=sandbox.repo_path,
                vfs=VirtualFs(sandbox.repo_path),
                dry_run=run.dry_run,
                project=project,
                run=run,
            )

            graph = flow.graph or {}
            nodes_by_id = {n["id"]: n for n in graph.get("nodes", [])}
            edges = graph.get("edges", [])
            execution_order = _topological_order(graph)

            run.plan = {"nodes": graph.get("nodes", []), "edges": edges}
            await session.commit()
            await bus.publish(RunEvent(run_id=run.id, type="plan.ready", payload=run.plan))

            sequence = 0
            attempts: dict[str, int] = {}

            for node_id in execution_order:
                node = nodes_by_id[node_id]
                attempts[node_id] = attempts.get(node_id, 0) + 1
                sequence += 1
                if not await self._dispatch_node(
                    session=session,
                    run=run,
                    node=node,
                    sequence=sequence,
                    attempt=attempts[node_id],
                    ctx=ctx,
                    agents_by_role=agents_by_role,
                    providers_list=providers_list,
                    models_by_provider=models_by_provider,
                ):
                    return

            run.status = "succeeded"
            run.finished_at = datetime.now(UTC)
            await session.commit()
            await bus.publish(RunEvent(run_id=run.id, type="run.finished", payload={"status": "succeeded"}))

    async def _dispatch_node(
        self,
        *,
        session: AsyncSession,
        run: Run,
        node: dict[str, Any],
        sequence: int,
        attempt: int,
        ctx: RunContext,
        agents_by_role: dict[str, Agent],
        providers_list: list[Provider],
        models_by_provider: dict[str, list[ProviderModel]],
    ) -> bool:
        node_id = node["id"]
        node_type = node.get("type", "agent")
        agent: Agent | None = None
        if node_type == "agent":
            role = node.get("agent_role") or node_id
            agent = agents_by_role.get(role)

        dry = is_dry_run(run, agent, node) or (run.dry_run and step_is_side_effecting(node))

        step = RunStep(
            workspace_id=run.workspace_id,
            run_id=run.id,
            node_id=node_id,
            agent_id=agent.id if agent else None,
            sequence=sequence,
            attempt=attempt,
            status="running",
            started_at=datetime.now(UTC),
            dry_run=dry,
        )
        session.add(step)
        await session.commit()

        await bus.publish(
            RunEvent(
                run_id=run.id,
                type="step.started",
                payload={"step_id": step.id, "node_id": node_id, "dry_run": dry, "attempt": attempt},
            )
        )

        if node_type == "wait_for_user":
            answer = await self._wait_for_user(session, run, step, node)
            ctx.scratchpad.setdefault("interventions", []).append({"node": node_id, "answer": answer})
            return await self._finish_step(session, run, step, StepResult(summary="user input received"))

        if node_type != "agent":
            return await self._finish_step(
                session, run, step, StepResult(summary=f"node type {node_type!r} ignored")
            )

        if not agent:
            return await self._finish_step(
                session,
                run,
                step,
                StepResult(summary=f"agent for role {node.get('agent_role')!r} not found", failed=True, error="missing agent"),
            )

        provider_model = pick_model(
            agent, providers_list, models_by_provider, ctx.issue, run.override_models or {}
        )
        if provider_model is None and agent.execution_adapter not in {"builtin", "opencode_cli", "gh_copilot_cli"}:
            return await self._finish_step(
                session,
                run,
                step,
                StepResult(summary="no provider/model available", failed=True, error="no usable provider"),
            )
        provider = provider_model[0] if provider_model else None
        chosen_model = provider_model[1] if provider_model else None

        resolved = ResolvedModel(
            provider_id=provider.id if provider else "",
            provider_kind=provider.kind if provider else "",
            model_id=chosen_model.model_id if chosen_model else "",
            base_url=provider.base_url if provider else None,
            api_key=secrets.get(provider.api_key_secret_ref) if provider and provider.api_key_secret_ref else None,
            extra=dict(provider.config or {}) if provider else {},
        )
        ctx.dry_run = dry

        try:
            adapter = adapters().get(agent.execution_adapter)
        except KeyError as exc:
            return await self._finish_step(
                session, run, step, StepResult(summary="bad adapter", failed=True, error=str(exc))
            )

        async def _publish_step_log(stream: str, line: str) -> None:
            await bus.publish(
                RunEvent(
                    run_id=run.id,
                    type="step.log",
                    payload={"step_id": step.id, "stream": stream, "line": line},
                ),
                persist=False,
            )

        try:
            with shell_line_subscriber(_publish_step_log):
                result = await adapter.run(ctx, agent, resolved)
        except Exception as exc:
            log.exception("step failed")
            result = StepResult(summary="step crashed", failed=True, error=str(exc))

        if chosen_model:
            result.cost_usd = estimate_cost_usd(
                result.tokens_in,
                result.tokens_out,
                chosen_model.input_cost_per_mtok,
                chosen_model.output_cost_per_mtok,
            )

        ok = await self._finish_step(session, run, step, result, provider_id=resolved.provider_id or None)
        if not ok and attempt < MAX_STEP_RETRIES and (agent.config or {}).get("retry_on_failure", True):
            await bus.publish(
                RunEvent(run_id=run.id, type="step.retry", payload={"node_id": node_id, "attempt": attempt + 1})
            )
            ctx.scratchpad["last_failure"] = result.error
            return await self._dispatch_node(
                session=session,
                run=run,
                node=node,
                sequence=sequence + 1,
                attempt=attempt + 1,
                ctx=ctx,
                agents_by_role=agents_by_role,
                providers_list=providers_list,
                models_by_provider=models_by_provider,
            )
        return ok

    async def _finish_step(
        self,
        session: AsyncSession,
        run: Run,
        step: RunStep,
        result: StepResult,
        *,
        provider_id: str | None = None,
    ) -> bool:
        step.status = "failed" if result.failed else "succeeded"
        step.finished_at = datetime.now(UTC)
        step.summary = result.summary
        step.error = result.error
        step.tokens_in = result.tokens_in
        step.tokens_out = result.tokens_out
        step.cost_estimate_usd = result.cost_usd
        step.model_used = result.model_used
        step.provider_id = provider_id or result.provider_id

        for art in result.artifacts:
            session.add(
                RunArtifact(
                    workspace_id=run.workspace_id,
                    run_step_id=step.id,
                    kind=art.get("kind", "response"),
                    name=art.get("name", "artifact"),
                    inline_content=art.get("inline_content"),
                    content_ref=art.get("content_ref"),
                    meta=art.get("meta", {}),
                )
            )

        run.total_tokens_in += result.tokens_in
        run.total_tokens_out += result.tokens_out
        run.cost_estimate_usd += result.cost_usd
        await session.commit()

        await bus.publish(
            RunEvent(
                run_id=run.id,
                type="step.finished",
                payload={
                    "step_id": step.id,
                    "node_id": step.node_id,
                    "status": step.status,
                    "summary": step.summary,
                    "error": step.error,
                    "tokens_in": step.tokens_in,
                    "tokens_out": step.tokens_out,
                    "cost_usd": step.cost_estimate_usd,
                    "model_used": step.model_used,
                    "warnings": result.warnings,
                    "artifacts": [
                        {
                            "kind": art.get("kind", "response"),
                            "name": art.get("name", "artifact"),
                            "preview": (art.get("inline_content") or "")[:1000],
                        }
                        for art in result.artifacts
                    ],
                },
            )
        )

        if result.failed:
            run.status = "failed"
            run.error = result.error
            run.finished_at = datetime.now(UTC)
            await session.commit()
            await bus.publish(
                RunEvent(run_id=run.id, type="run.failed", payload={"error": result.error, "node_id": step.node_id})
            )
        return not result.failed

    async def _wait_for_user(
        self, session: AsyncSession, run: Run, step: RunStep, node: dict[str, Any]
    ) -> dict[str, Any]:
        prompt = (node.get("config") or {}).get("prompt") or "Provide additional context for this run."
        intervention = Intervention(
            workspace_id=run.workspace_id,
            run_id=run.id,
            run_step_id=step.id,
            kind="question",
            prompt=prompt,
            options=(node.get("config") or {}).get("options", []),
        )
        session.add(intervention)
        await session.commit()
        pending = await intervention_registry.register(intervention.id)
        await bus.publish(
            RunEvent(
                run_id=run.id,
                type="intervention.requested",
                payload={
                    "intervention_id": intervention.id,
                    "step_id": step.id,
                    "prompt": prompt,
                    "options": intervention.options,
                },
            )
        )
        answer = await intervention_registry.wait(intervention.id, timeout=None)
        intervention.answer = answer
        intervention.status = "answered"
        intervention.answered_at = datetime.now(UTC)
        await session.commit()
        await bus.publish(
            RunEvent(
                run_id=run.id,
                type="intervention.resolved",
                payload={"intervention_id": intervention.id, "answer": answer},
            )
        )
        await intervention_registry.discard(intervention.id)
        return answer or {}


def _topological_order(graph: dict[str, Any]) -> list[str]:
    """Simple Kahn's-algorithm topo sort. Cycles fall back to insertion order."""
    nodes = [n["id"] for n in graph.get("nodes", [])]
    edges = graph.get("edges", []) or []
    indegree: dict[str, int] = {n: 0 for n in nodes}
    successors: dict[str, list[str]] = {n: [] for n in nodes}
    for e in edges:
        s, t = e.get("source"), e.get("target")
        if s in indegree and t in indegree and not e.get("condition", "").startswith("tests.failed"):
            successors[s].append(t)
            indegree[t] += 1
    ready = [n for n, d in indegree.items() if d == 0]
    order: list[str] = []
    while ready:
        n = ready.pop(0)
        if n in order:
            continue
        order.append(n)
        for succ in successors.get(n, []):
            indegree[succ] -= 1
            if indegree[succ] == 0:
                ready.append(succ)
    for n in nodes:
        if n not in order:
            order.append(n)
    return order


run_manager = RunEngine()


def serialize_event(evt: RunEvent) -> str:
    return json.dumps(evt.to_dict(), default=str)
