"""Runs router: start, status, intervene, retry, cancel, summary export."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Flow, Intervention, Issue, Project, Run, RunArtifact, RunStep, Workspace
from ..orchestrator import run_manager
from ..orchestrator.events import bus
from ..orchestrator.intervention import registry as intervention_registry
from .deps import db_session, workspace
from .schemas import (
    InterventionAnswer,
    InterventionOut,
    RunDetail,
    RunOut,
    RunStartRequest,
    RunStepOut,
)

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.get("", response_model=list[RunOut])
async def list_runs(
    project_id: str | None = None,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> list[RunOut]:
    stmt = select(Run).where(Run.workspace_id == ws.id).order_by(Run.created_at.desc())
    if project_id:
        stmt = stmt.where(Run.project_id == project_id)
    res = await session.execute(stmt)
    return [RunOut.model_validate(r) for r in res.scalars()]


@router.post("", response_model=RunOut, status_code=201)
async def create_run(
    payload: RunStartRequest,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> RunOut:
    project = await session.get(Project, payload.project_id)
    if not project or project.workspace_id != ws.id:
        raise HTTPException(404, "Project not found")

    flow_id = payload.flow_id or project.default_flow_id
    if not flow_id:
        res = await session.execute(
            select(Flow).where(Flow.workspace_id == ws.id, Flow.is_default == True)  # noqa: E712
        )
        flow = res.scalar_one_or_none()
    else:
        flow = await session.get(Flow, flow_id)
    if not flow or flow.workspace_id != ws.id:
        raise HTTPException(400, "No flow available for this run")

    issue_id = payload.issue_id
    issue_number = payload.issue_number
    if issue_id and not issue_number:
        issue = await session.get(Issue, issue_id)
        if issue:
            issue_number = issue.number

    run = Run(
        workspace_id=ws.id,
        project_id=project.id,
        flow_id=flow.id,
        issue_id=issue_id,
        issue_number=issue_number,
        title=payload.title or (f"Run for issue #{issue_number}" if issue_number else "Run"),
        status="pending",
        dry_run=payload.dry_run,
        override_models=payload.override_models,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    await run_manager.start(run.id)
    return RunOut.model_validate(run)


@router.get("/{run_id}", response_model=RunDetail)
async def get_run(
    run_id: str,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> RunDetail:
    run = await session.get(Run, run_id)
    if not run or run.workspace_id != ws.id:
        raise HTTPException(404, "Run not found")
    steps = list(
        (await session.execute(select(RunStep).where(RunStep.run_id == run.id).order_by(RunStep.sequence))).scalars()
    )
    detail = RunDetail.model_validate(run)
    detail.steps = [RunStepOut.model_validate(s) for s in steps]
    return detail


@router.post("/{run_id}/cancel")
async def cancel_run(
    run_id: str,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> dict[str, bool]:
    run = await session.get(Run, run_id)
    if not run or run.workspace_id != ws.id:
        raise HTTPException(404, "Run not found")
    cancelled = await run_manager.cancel(run.id)
    if cancelled:
        run.status = "cancelled"
        run.finished_at = datetime.now(UTC)
        await session.commit()
    return {"cancelled": cancelled}


@router.post("/{run_id}/retry", response_model=RunOut)
async def retry_run(
    run_id: str,
    dry_run: bool | None = None,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> RunOut:
    src = await session.get(Run, run_id)
    if not src or src.workspace_id != ws.id:
        raise HTTPException(404, "Run not found")
    new_run = Run(
        workspace_id=ws.id,
        project_id=src.project_id,
        flow_id=src.flow_id,
        issue_id=src.issue_id,
        issue_number=src.issue_number,
        title=f"Retry of {src.title}",
        status="pending",
        dry_run=src.dry_run if dry_run is None else dry_run,
        override_models=src.override_models,
    )
    session.add(new_run)
    await session.commit()
    await session.refresh(new_run)
    await run_manager.start(new_run.id)
    return RunOut.model_validate(new_run)


@router.get("/{run_id}/interventions", response_model=list[InterventionOut])
async def list_interventions(
    run_id: str,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> list[InterventionOut]:
    run = await session.get(Run, run_id)
    if not run or run.workspace_id != ws.id:
        raise HTTPException(404, "Run not found")
    res = await session.execute(
        select(Intervention).where(Intervention.run_id == run.id).order_by(Intervention.created_at)
    )
    return [InterventionOut.model_validate(i) for i in res.scalars()]


@router.post("/{run_id}/interventions/{intervention_id}", response_model=InterventionOut)
async def answer_intervention(
    run_id: str,
    intervention_id: str,
    payload: InterventionAnswer,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> InterventionOut:
    intervention = await session.get(Intervention, intervention_id)
    if not intervention or intervention.workspace_id != ws.id or intervention.run_id != run_id:
        raise HTTPException(404, "Intervention not found")
    if intervention.status == "answered":
        return InterventionOut.model_validate(intervention)
    await intervention_registry.answer(intervention.id, payload.answer)
    intervention.status = "answered"
    intervention.answer = payload.answer
    intervention.answered_at = datetime.now(UTC)
    await session.commit()
    return InterventionOut.model_validate(intervention)


@router.get("/{run_id}/summary")
async def summary(
    run_id: str,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> JSONResponse:
    run = await session.get(Run, run_id)
    if not run or run.workspace_id != ws.id:
        raise HTTPException(404, "Run not found")
    steps = list(
        (await session.execute(select(RunStep).where(RunStep.run_id == run.id).order_by(RunStep.sequence))).scalars()
    )
    artifacts = list(
        (
            await session.execute(
                select(RunArtifact).where(RunArtifact.run_step_id.in_([s.id for s in steps]))
            )
        ).scalars()
    )
    payload = {
        "run": json.loads(RunOut.model_validate(run).model_dump_json()),
        "steps": [json.loads(RunStepOut.model_validate(s).model_dump_json()) for s in steps],
        "artifact_count": len(artifacts),
        "totals": {
            "tokens_in": run.total_tokens_in,
            "tokens_out": run.total_tokens_out,
            "cost_usd": run.cost_estimate_usd,
        },
    }
    return JSONResponse(payload)


@router.get("/{run_id}/summary.md", response_class=PlainTextResponse)
async def summary_markdown(
    run_id: str,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> PlainTextResponse:
    run = await session.get(Run, run_id)
    if not run or run.workspace_id != ws.id:
        raise HTTPException(404, "Run not found")
    steps = list(
        (await session.execute(select(RunStep).where(RunStep.run_id == run.id).order_by(RunStep.sequence))).scalars()
    )
    lines: list[str] = []
    lines.append(f"# Run summary — {run.title}")
    lines.append("")
    lines.append(f"- **Run id:** `{run.id}`")
    lines.append(f"- **Status:** `{run.status}`{' (dry-run)' if run.dry_run else ''}")
    lines.append(f"- **Started:** {run.started_at.isoformat() if run.started_at else '—'}")
    lines.append(f"- **Finished:** {run.finished_at.isoformat() if run.finished_at else '—'}")
    if run.issue_number:
        lines.append(f"- **Issue:** #{run.issue_number}")
    lines.append(
        f"- **Tokens:** in={run.total_tokens_in} out={run.total_tokens_out} "
        f"· estimated cost ${run.cost_estimate_usd:.4f}"
    )
    if run.error:
        lines.append(f"- **Error:** {run.error}")
    lines.append("")
    lines.append("## Steps")
    lines.append("")
    lines.append("| # | Node | Status | Model | Tokens (in/out) | Cost |")
    lines.append("|---|------|--------|-------|-----------------|------|")
    for s in steps:
        model = s.model_used or "—"
        lines.append(
            f"| {s.sequence} | `{s.node_id}` | {s.status}{'·dry' if s.dry_run else ''} | "
            f"{model} | {s.tokens_in}/{s.tokens_out} | ${s.cost_estimate_usd:.4f} |"
        )
    lines.append("")
    failed = [s for s in steps if s.status == "failed"]
    if failed:
        lines.append("## Failures")
        for s in failed:
            lines.append(f"- `{s.node_id}` — {s.error}")
    return PlainTextResponse("\n".join(lines))


@router.get("/{run_id}/audit")
async def run_audit(
    run_id: str,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> JSONResponse:
    """Full event history for a run, durable from the in-memory bus.

    Useful for the audit-log view in the UI.
    """
    run = await session.get(Run, run_id)
    if not run or run.workspace_id != ws.id:
        raise HTTPException(404, "Run not found")
    history = bus.history(run.id)
    return JSONResponse([evt.to_dict() for evt in history])


@router.post("/{run_id}/promote", response_model=RunOut, status_code=201)
async def promote_dry_run(
    run_id: str,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> RunOut:
    """Promote a successful dry-run into a real, side-effecting run.

    Spawns a fresh, non-dry-run that re-uses the same flow / project / issue
    bindings, so the user can review the dry-run plan first and then commit.
    """
    src = await session.get(Run, run_id)
    if not src or src.workspace_id != ws.id:
        raise HTTPException(404, "Run not found")
    if not src.dry_run:
        raise HTTPException(400, "Source run is not a dry-run")
    if src.status not in {"succeeded", "failed", "cancelled"}:
        raise HTTPException(400, "Wait for the dry-run to finish before promoting")
    promoted = Run(
        workspace_id=ws.id,
        project_id=src.project_id,
        flow_id=src.flow_id,
        issue_id=src.issue_id,
        issue_number=src.issue_number,
        title=f"Promoted: {src.title}",
        status="pending",
        dry_run=False,
        override_models=src.override_models,
    )
    session.add(promoted)
    await session.commit()
    await session.refresh(promoted)
    await run_manager.start(promoted.id)
    return RunOut.model_validate(promoted)


@router.get("/{run_id}/steps/{step_id}/artifacts")
async def step_artifacts(
    run_id: str,
    step_id: str,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> list[dict]:
    run = await session.get(Run, run_id)
    if not run or run.workspace_id != ws.id:
        raise HTTPException(404, "Run not found")
    res = await session.execute(
        select(RunArtifact).where(RunArtifact.run_step_id == step_id).order_by(RunArtifact.created_at)
    )
    return [
        {
            "id": a.id,
            "kind": a.kind,
            "name": a.name,
            "inline_content": a.inline_content,
            "content_ref": a.content_ref,
            "meta": a.meta,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in res.scalars()
    ]
