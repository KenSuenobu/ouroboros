#!/usr/bin/env python3
"""Create the full ticket inventory for KenSuenobu/ouroboros.

Idempotent and resumable. State is kept in `scripts/.issues_state.json`
inside the working tree so re-running skips items already created.

Usage:
    python3 scripts/create_issues.py            # creates everything
    python3 scripts/create_issues.py --rewrite  # only rewrite the roadmap MD

Requires: gh CLI authenticated, repo already pushed.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO = "KenSuenobu/ouroboros"
ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = Path(__file__).resolve().parent / ".issues_state.json"
ROADMAP = ROOT / "PLANNED_FEATURE_ROADMAP_2026.md"

LABELS: list[tuple[str, str, str]] = [
    ("tier:mvp", "B60205", "Required for the first usable release"),
    ("tier:post-mvp", "0E8A16", "Required for daily-use polish after MVP"),
    ("tier:cloud", "1D76DB", "Cloud Solo / Cloud Team only"),
    ("tier:enterprise", "5319E7", "Enterprise tier (on-prem / VPC) only"),
    ("tier:research", "FBCA04", "Stretch / research idea, not committed"),
    ("type:epic", "C5DEF5", "Stage-level epic; tracks a checklist of child issues"),
    ("stage:1", "EDEDED", "Stage 1 - MVP correctness & onboarding"),
    ("stage:2", "EDEDED", "Stage 2 - UX & power-user features"),
    ("stage:3", "EDEDED", "Stage 3 - Quality, observability, operability"),
    ("stage:4", "EDEDED", "Stage 4 - Cloud (Solo / Team)"),
    ("stage:5", "EDEDED", "Stage 5 - Enterprise"),
    ("stage:stretch", "EDEDED", "Stretch / research"),
]

STAGES: list[dict[str, Any]] = [
    {
        "key": "stage-1",
        "stage_label": "stage:1",
        "milestone": "Stage 1 - MVP",
        "epic_title": "Epic: Stage 1 - MVP correctness & onboarding",
        "summary": (
            "Polish the smallest end-to-end loop so a new user can install Ouroboros, "
            "point it at a project, and have an agent run the first issue without "
            "hand-editing config."
        ),
        "outcome": (
            "A first-time user can go from `make install` to a successful dry-run "
            "against a real GitHub issue in under five minutes."
        ),
    },
    {
        "key": "stage-2",
        "stage_label": "stage:2",
        "milestone": "Stage 2 - UX & power-user",
        "epic_title": "Epic: Stage 2 - UX & power-user features",
        "summary": (
            "Once the loop works, make it pleasant for daily use: comparisons, "
            "batching, notifications, smarter planning, deeper SCM coverage, and "
            "the run -> flow -> run feedback cycle."
        ),
        "outcome": (
            "Daily-driver users can run dozens of issues per week with minimal "
            "babysitting and progressively codify their workflows as Flows."
        ),
    },
    {
        "key": "stage-3",
        "stage_label": "stage:3",
        "milestone": "Stage 3 - Quality & ops",
        "epic_title": "Epic: Stage 3 - Quality, observability, operability",
        "summary": (
            "Make Ouroboros operable at scale: structured logs, metrics, traces, "
            "backup/restore, hardened sandbox, configurable price catalog."
        ),
        "outcome": (
            "An SRE can deploy Ouroboros, monitor it via Prometheus/OTLP, "
            "back it up, and prove its dry-run guarantees under fuzz + adversarial "
            "test pressure."
        ),
    },
    {
        "key": "stage-4",
        "stage_label": "stage:4",
        "milestone": "Stage 4 - Cloud",
        "epic_title": "Epic: Stage 4 - Cloud (Solo / Team)",
        "summary": (
            "Wire the multi-tenant cloud surface: auth, RBAC, shared providers, "
            "Stripe metering, managed-models proxy, S3 artifacts, audit export, "
            "webhooks, and API tokens."
        ),
        "outcome": (
            "Customers can sign up with GitHub OAuth, invite teammates with role "
            "control, and pay either BYOK seat fees or metered managed inference."
        ),
    },
    {
        "key": "stage-5",
        "stage_label": "stage:5",
        "milestone": "Stage 5 - Enterprise",
        "epic_title": "Epic: Stage 5 - Enterprise",
        "summary": (
            "Cross the line into regulated / on-prem deployments: SSO, SCIM, BYOK "
            "KMS, air-gapped mode, OPA policies, data residency, mTLS, "
            "tamper-evident audit, retention policies, helm chart, customer "
            "model gateway, SOC 2 evidence."
        ),
        "outcome": (
            "Ouroboros can be deployed inside a customer VPC with their identity "
            "provider, key store, network policy, and compliance posture."
        ),
    },
    {
        "key": "stretch",
        "stage_label": "stage:stretch",
        "milestone": "Stretch / Research",
        "epic_title": "Epic: Stretch / research",
        "summary": (
            "Exploratory ideas not committed to any stage. Track them as issues "
            "so we don't lose context, but expect long-running research before "
            "any of them ships."
        ),
        "outcome": (
            "A small set of de-risking spikes that inform later product bets "
            "(self-improving router, agent benchmarks, learned cost predictor, "
            "local review gate, IDE plugins)."
        ),
    },
]


@dataclass
class Ticket:
    key: str
    stage: str
    tier: str
    title: str
    problem: str
    scope: list[str]
    tech: list[str]
    accept: list[str]
    parallel: str
    deps: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Tickets. Order matters only for human readability; numbers are assigned by
# GitHub. The `parallel` field describes whether other agents/devs can pick up
# adjacent work concurrently. `deps` lists ticket keys that must land first.
# ---------------------------------------------------------------------------

TICKETS: list[Ticket] = [
    # ----- STAGE 1: MVP correctness & onboarding -----
    Ticket(
        key="TBD-01",
        stage="stage-1",
        tier="MVP",
        title="First-run onboarding wizard (workspace -> project -> first provider)",
        problem=(
            "A new user lands on `/projects` with an empty database and no idea what "
            "to do first. They have to discover Providers, Agents, and Flows in the "
            "right order before anything works."
        ),
        scope=[
            "Three-step modal: 1) name your workspace, 2) connect a project (repo URL + SCM kind), 3) connect at least one provider (Ollama default URL or paste an Anthropic key).",
            "Skippable but resurfaces until at least one project + provider exist.",
            "Persists `onboarding_completed_at` on the Workspace row.",
        ],
        tech=[
            "New component `apps/web/src/components/onboarding/wizard.tsx` rendered from `app/layout.tsx` when needed.",
            "New endpoint `GET /api/workspaces/me` returns onboarding status; `POST /api/workspaces/me/onboarding` writes it.",
            "Wizard reuses existing Project + Provider create endpoints; no new orchestrator code.",
        ],
        accept=[
            "Fresh DB -> opening the app shows the wizard immediately.",
            "Completing all steps creates the rows and never shows the wizard again.",
            "Skipping returns the user to it on next page load until a project + provider exist.",
        ],
        parallel="Parallelisable with all other Stage 1 tickets; no shared files beyond `app/layout.tsx`.",
    ),
    Ticket(
        key="TBD-02",
        stage="stage-1",
        tier="MVP",
        title="Provider healthcheck panel (ping each provider, surface errors)",
        problem=(
            "Today a misconfigured provider only fails mid-run, deep inside an agent step. "
            "Users have no way to verify Ollama is reachable or that an Anthropic key is valid "
            "before kicking off work."
        ),
        scope=[
            "Per-provider status badge on `/providers`: ok / unreachable / unauthorized / no-models.",
            "Click a badge -> see the raw error from the last health probe.",
            "Auto-probe on provider create/edit; manual `Refresh` button always available.",
        ],
        tech=[
            "New endpoint `GET /api/providers/{id}/health` issues a tiny request per kind: Ollama `/api/tags`, Anthropic `/v1/messages` HEAD, GitHub Models `/catalog/models`.",
            "Persist last result in `Provider.last_health_*` columns (added via Alembic).",
            "Frontend: status badge on `apps/web/src/app/providers/page.tsx` + a `/health` summary page that lists every provider.",
        ],
        accept=[
            "Misconfigured Anthropic key shows `unauthorized` badge with the API error message visible on hover.",
            "Stopping Ollama transitions the badge to `unreachable` within one refresh cycle.",
            "All-green state is rendered with a single check icon, no tooltip noise.",
        ],
        parallel="Parallelisable with TBD-01, TBD-04, TBD-06; touches `Provider` model so coordinate with anyone else editing that table.",
    ),
    Ticket(
        key="TBD-03",
        stage="stage-1",
        tier="MVP",
        title="Auto-detect repo build/test commands (package.json, pyproject, Makefile)",
        problem=(
            "Project creation requires the user to type `build_command` and `test_command`. "
            "Most repos already declare these; we should pre-fill them."
        ),
        scope=[
            "On project create / sync, scan the cloned repo (or fetch raw files via SCM API) for: `package.json` scripts, `pyproject.toml` `[tool.*]` test commands, `Makefile` targets, `Cargo.toml`, `go.mod`.",
            "Suggest commands in the Project edit form with a clickable `Use this` chip per finding.",
            "Never overwrite a user-set command; suggestions are advisory only.",
        ],
        tech=[
            "New module `apps/api/ouroboros_api/services/repo_introspect.py` returning `{build: [...candidates], test: [...candidates]}`.",
            "New endpoint `GET /api/projects/{id}/introspect` cached for 1h.",
            "Frontend: `apps/web/src/app/projects/page.tsx` shows the chips next to the build/test fields.",
        ],
        accept=[
            "A Next.js repo suggests `next build` and `next test` (or `vitest run`).",
            "A `pyproject.toml` with `[tool.pytest.ini_options]` suggests `uv run pytest -q`.",
            "A repo with no recognised manifest returns an empty suggestion set; the form still works.",
        ],
        parallel="Independent; only touches new files plus the project page.",
    ),
    Ticket(
        key="TBD-04",
        stage="stage-1",
        tier="MVP",
        title="Default per-language router policy on every seed agent",
        problem=(
            "Only the seeded `coder` agent has language hints today. Other agents (planner, "
            "verifier, summarizer) fall back to the first enabled provider regardless of task."
        ),
        scope=[
            "Add `model_policy.router_hints.language_map` defaults to all seed agents that benefit (planner, summarizer, audit, coder).",
            "Per-language defaults: Python -> Anthropic Sonnet for planning / Ollama qwen-coder for coding; TypeScript -> Anthropic for both; SQL -> Ollama sqlcoder for coding.",
            "Document the choice in the agent's `description`.",
        ],
        tech=[
            "Edit `apps/api/ouroboros_api/seeds/agents.py` to add hints.",
            "Migration is not needed if the bootstrap re-seeds; for already-seeded DBs add a one-shot Alembic data migration that updates rows where `model_policy.router_hints` is empty.",
        ],
        accept=[
            "Seed bootstrap into an empty DB sets language maps on all four agents.",
            "An issue mentioning `src/foo.py` runs the planner under Anthropic and the coder under Ollama qwen.",
            "User overrides on the run launcher still take precedence (verified by an existing test).",
        ],
        parallel="Pairs naturally with TBD-11 (router presets); they share the policy schema but not the seed file.",
    ),
    Ticket(
        key="TBD-05",
        stage="stage-1",
        tier="MVP",
        title="Real-time stdout/stderr streaming for shell steps",
        problem=(
            "Shell steps (build / test) buffer their output and only emit one final blob. "
            "On long-running builds the user has no progress signal."
        ),
        scope=[
            "Stream each line of stdout/stderr as a `step.log` event over the run WebSocket.",
            "Run-detail page shows a live, auto-scrolling log pane per running shell step.",
            "Final aggregated log is still saved as a `RunArtifact` for after-the-fact viewing.",
        ],
        tech=[
            "Refactor `apps/api/ouroboros_api/sandbox/shell.py` to expose an async iterator of (stream, line) tuples.",
            "Engine subscribes and emits `RunEvent(type='step.log', payload={'step_id', 'stream', 'line'})`.",
            "Frontend `apps/web/src/components/runs/log-pane.tsx` (new) consumes events from `use-run-stream` filtered by step.",
        ],
        accept=[
            "`yarn dev` of a real test target shows lines arriving within 200ms.",
            "Cancelling the run terminates the subprocess and closes the stream.",
            "After completion the full log is still retrievable via `/runs/{id}/steps/{step_id}/artifacts`.",
        ],
        parallel="Independent; the only shared surface is the WebSocket event schema, which is open-ended by design.",
    ),
    Ticket(
        key="TBD-06",
        stage="stage-1",
        tier="MVP",
        title="`ouroboros init` CLI to write `.env` with sensible defaults",
        problem=(
            "Today envs like `OUROBOROS_DB_URL` and `OUROBOROS_DATA_DIR` are read but never "
            "written. New users have to grep the source to learn they exist."
        ),
        scope=[
            "New CLI subcommand `ouroboros init` that prompts for data dir and DB URL (defaults to `./data` and `sqlite+aiosqlite:///./data/ouroboros.sqlite`).",
            "Writes a `.env` and a `.env.example` next to it; safe-fails if `.env` already exists.",
            "Documents itself in the README quick-start.",
        ],
        tech=[
            "New `apps/cli/` Python package (or extend the existing `apps/api/ouroboros_api/main.py:run` entry point).",
            "Use `typer` or `click`; reuse `Settings` from `apps/api/ouroboros_api/config.py` for the defaults.",
        ],
        accept=[
            "`uv run ouroboros init` in an empty directory writes `.env` and exits 0.",
            "Re-running prints `\".env exists; not overwriting\"` and exits 0.",
            "README quick-start references the command as step 0.",
        ],
        parallel="Independent.",
    ),
    Ticket(
        key="TBD-07",
        stage="stage-1",
        tier="MVP",
        title="Resume button for runs interrupted mid-step",
        problem=(
            "If the API process restarts mid-run (laptop sleep, crash, deploy) the run is "
            "stuck in `running` forever. Users have to delete + re-create."
        ),
        scope=[
            "On API startup, mark in-flight runs as `interrupted` instead of `running`.",
            "Run detail page shows a `Resume` button on interrupted runs.",
            "Resume picks up from the first non-succeeded step using the persisted `RunContext` snapshot.",
        ],
        tech=[
            "Add `Run.snapshot_json` column for context (issue, scratchpad, override_models) - already partially in `RunContext`; persist it after every step.",
            "New endpoint `POST /api/runs/{id}/resume` re-enters `RunEngine._execute` skipping completed steps.",
            "On startup hook in `apps/api/ouroboros_api/main.py:lifespan`, run a sweep that flips `running` -> `interrupted`.",
        ],
        accept=[
            "Killing uvicorn mid-run, restarting, then clicking `Resume` continues from the next pending step.",
            "Already-succeeded steps are not re-executed.",
            "Resuming a dry-run stays a dry-run.",
        ],
        parallel="Couples with TBD-24 (replay). Land TBD-07 first; TBD-24 reuses the snapshot layer.",
        deps=[],
    ),
    Ticket(
        key="TBD-08",
        stage="stage-1",
        tier="MVP",
        title="True side-by-side dry-run diff viewer (Monaco DiffEditor)",
        problem=(
            "The current `DiffViewer` shows only the modified content, not original-vs-modified. "
            "Reviewing a dry-run is therefore harder than it should be."
        ),
        scope=[
            "Replace `DiffViewer` with a real Monaco `DiffEditor` showing original on the left, proposed on the right.",
            "Wire the `file_diff` artifact: original is read from the sandbox repo, proposed from `inline_content`.",
            "Inline mode toggle (side-by-side vs unified).",
        ],
        tech=[
            "Edit `apps/web/src/components/editors/diff-viewer.tsx` to use `@monaco-editor/react` `DiffEditor`.",
            "Backend artifact emitter must include `path` so the UI can fetch the original via a new `GET /api/runs/{id}/sandbox-file?path=...` endpoint.",
            "Add path-traversal guard on the new endpoint.",
        ],
        accept=[
            "Opening any `file_diff` artifact shows true left/right diff with syntax highlighting.",
            "Switching to unified mode reflows without reload.",
            "An attempt to read `../../etc/passwd` returns 400.",
        ],
        parallel="Independent.",
    ),

    # ----- STAGE 2: UX & power-user (17 tickets, all Post-MVP) -----
    Ticket(
        key="TBD-09",
        stage="stage-2",
        tier="Post-MVP",
        title="Side-by-side run comparison view",
        problem=(
            "Comparing the cost / quality of two model policies for the same issue requires "
            "opening two browser tabs and eyeballing it."
        ),
        scope=[
            "New page `/runs/compare?a=...&b=...` showing two runs in adjacent columns.",
            "Diff token spend, total cost, plan graph, per-step status, and final artifact bundles.",
            "Launch via a `Compare with...` action on any run card.",
        ],
        tech=[
            "New route `apps/web/src/app/runs/compare/page.tsx` reusing existing run hooks.",
            "Reuse `RunPlanFlow` rendered side-by-side.",
            "No backend change beyond the existing run detail endpoint.",
        ],
        accept=[
            "Picking any two runs renders both within 1s.",
            "Cost / token deltas are highlighted (red / green).",
            "Plan graphs scroll independently.",
        ],
        parallel="Independent.",
    ),
    Ticket(
        key="TBD-10",
        stage="stage-2",
        tier="Post-MVP",
        title="Cost forecast on the `Run this issue` button",
        problem=(
            "Users have no advance warning that a run might cost $5 vs $0.05 until after the fact."
        ),
        scope=[
            "Compute a per-flow average from prior runs (median tokens per step) -> multiply by current pricing.",
            "Show forecast inline on the launcher button: `Estimated ~$0.42 (median of 12 prior runs)`.",
            "Recompute when the user changes the model override.",
        ],
        tech=[
            "New endpoint `GET /api/projects/{id}/flows/{flow_id}/forecast?override_models=...`.",
            "Backed by a small Postgres/SQLite view on `RunStep` aggregated by node + model.",
            "Frontend: edit `apps/web/src/app/issues/page.tsx` to render the forecast next to the run button.",
        ],
        accept=[
            "First run on a flow shows `(no history yet)` with no error.",
            "After 5 runs the forecast appears and updates when overrides change.",
            "Forecast is bounded `[0.01, 1000]` USD - obviously bogus values are clamped with a warning.",
        ],
        parallel="Pairs with TBD-58 (learned cost predictor); the forecast endpoint can later swap to the predictor.",
    ),
    Ticket(
        key="TBD-11",
        stage="stage-2",
        tier="Post-MVP",
        title="Saved router presets shared across agents",
        problem=(
            "Today router hints live as JSON inside each agent. A user who wants `frontend stack` "
            "(Anthropic for planning, Anthropic for TS, Ollama for review) has to copy/paste."
        ),
        scope=[
            "New `RouterPreset` table: `{name, language_map, default_provider}`.",
            "Agent edit page can attach a preset by name; the resolved policy at runtime merges preset + per-agent overrides.",
            "Default presets seeded: `frontend`, `backend-python`, `data-eng`, `local-only`.",
        ],
        tech=[
            "Alembic migration adds the table.",
            "Edit `apps/api/ouroboros_api/orchestrator/router.py:pick_model` to apply preset hints.",
            "Frontend: dropdown on the agent edit page; new `/routing/presets` sub-page for CRUD.",
        ],
        accept=[
            "Switching the preset on three agents at once changes their actual provider on the next run.",
            "Per-agent overrides still win over preset hints.",
            "Deleting a preset that is still referenced returns 409 with the offending agents listed.",
        ],
        parallel="Land after TBD-04. Touches `pick_model` so coordinate with TBD-19 (failover).",
        deps=["TBD-04"],
    ),
    Ticket(
        key="TBD-12",
        stage="stage-2",
        tier="Post-MVP",
        title="Inline issue triage: rewrite acceptance criteria before launching the run",
        problem=(
            "Issue bodies often lack acceptance criteria; users edit them on GitHub before "
            "running, which is slow and pollutes the issue history."
        ),
        scope=[
            "On the issue detail pane, expose an editable `Run-time overrides` markdown box.",
            "Override text is appended to the issue body sent into the planner; the original GitHub issue is not modified.",
            "Persisted on `Run.issue_overrides` so the audit trail is intact.",
        ],
        tech=[
            "Add `Run.issue_overrides` text column.",
            "Edit `apps/api/ouroboros_api/orchestrator/context.py:RunContext.issue` to surface overrides to all downstream agents.",
            "Frontend: Monaco markdown editor on `apps/web/src/app/issues/page.tsx`.",
        ],
        accept=[
            "Adding override text and launching shows it inside the planner artifact.",
            "GitHub issue body is never touched.",
            "Re-running a previous run preserves its overrides.",
        ],
        parallel="Independent.",
    ),
    Ticket(
        key="TBD-13",
        stage="stage-2",
        tier="Post-MVP",
        title="Multi-issue batch runs with global concurrency cap",
        problem=(
            "Users want to queue 5 issues at once and walk away. Today they must launch them "
            "one by one and they will all start simultaneously, blowing the provider rate limit."
        ),
        scope=[
            "Issue list supports multi-select -> `Run all (dry-run)` button.",
            "Engine respects a global `max_concurrent_runs` setting (default 2).",
            "Pending runs queue visibly on the Runs page with `position` indicators.",
        ],
        tech=[
            "Add `Run.queued_at` and a tiny scheduler in `RunEngine.start` that defers spawn if `_count_running() >= settings.max_concurrent_runs`.",
            "Settings: `OUROBOROS_MAX_CONCURRENT_RUNS=2`.",
            "Frontend: multi-select state on the issues page.",
        ],
        accept=[
            "Selecting 5 issues and clicking `Run all` enqueues 5 runs; only 2 enter `running` at a time.",
            "Cancelling a queued run removes it without spawning.",
            "Cap can be raised at runtime via env without restart (re-read on next schedule cycle).",
        ],
        parallel="Pairs with TBD-33 (rate-limit backpressure).",
    ),
    Ticket(
        key="TBD-14",
        stage="stage-2",
        tier="Post-MVP",
        title="Notification adapters: webhook, Slack, email, Linear",
        problem=(
            "Users want to know when a long run finishes. Today they sit watching the UI."
        ),
        scope=[
            "New `NotificationAdapter` abstract base; concrete `WebhookAdapter`, `SlackAdapter`, `EmailAdapter`, `LinearAdapter`.",
            "Per-workspace notification rules: `on={run.failed,run.succeeded,intervention.requested}`, `via=[adapter ids]`.",
            "Failure to deliver retries with exponential backoff and surfaces in the audit log.",
        ],
        tech=[
            "New module `apps/api/ouroboros_api/notifications/`.",
            "Wired off the existing `RunEventBus` so no engine changes are needed.",
            "Frontend: new `/notifications` page with a wizard per adapter type.",
        ],
        accept=[
            "Configuring Slack and triggering a failed run posts a message within 5s.",
            "A 429 from Slack triggers up to 3 retries then logs to `data/logs/notifications.jsonl`.",
            "Removing an adapter does not affect in-flight retries.",
        ],
        parallel="Independent. Pairs naturally with TBD-42 (cloud webhook delivery) which generalises this.",
    ),
    Ticket(
        key="TBD-15",
        stage="stage-2",
        tier="Post-MVP",
        title="`require_approval` node type on the flow graph",
        problem=(
            "Some teams want a human gate before any side-effecting step (commit/push). Today "
            "the only way is to set the whole run to dry-run."
        ),
        scope=[
            "New control node type `require_approval` rendered in the routing designer.",
            "When the engine reaches one, it pauses and emits an intervention with options `Approve` / `Reject`.",
            "Reject -> run terminates as `cancelled` with reason `human-rejected`.",
        ],
        tech=[
            "Extend `apps/api/ouroboros_api/orchestrator/engine.py` to handle the new node type via the existing intervention machinery.",
            "Update `apps/web/src/components/flow/flow-designer.tsx` palette to include the node.",
            "Schema: extend `FlowNode.type` enum.",
        ],
        accept=[
            "A flow with the node pauses; the UI shows the approval modal.",
            "Approve continues; Reject ends the run.",
            "Dry-runs ignore the node (already non-side-effecting).",
        ],
        parallel="Independent.",
    ),
    Ticket(
        key="TBD-16",
        stage="stage-2",
        tier="Post-MVP",
        title="Diff-aware planner: feed structured repo summary instead of full repo dump",
        problem=(
            "The planner today often gets the full file tree dumped into context, costing huge "
            "token budgets on large repos."
        ),
        scope=[
            "New `RepoSummary` builder: file tree (depth-limited), `git log -n 10 --stat`, top-level READMEs, language stats.",
            "Planner system prompt receives a compact JSON summary instead of raw files.",
            "Configurable per agent via `agent.config.context_strategy=summary|full`.",
        ],
        tech=[
            "New module `apps/api/ouroboros_api/services/repo_summary.py`.",
            "Wire into the LLM agent loop's prompt assembly stage.",
            "Token budget verification via existing tiktoken calls.",
        ],
        accept=[
            "Planner runs against a 100k-file repo without exceeding 200k input tokens.",
            "Summary mode is the default for new flows; existing flows keep their current setting.",
            "A unit test asserts deterministic summary output for a fixture repo.",
        ],
        parallel="Independent.",
    ),
    Ticket(
        key="TBD-17",
        stage="stage-2",
        tier="Post-MVP",
        title="Sandbox snapshotting via `git worktree`",
        problem=(
            "Each run does a full `git clone`. On a 1GB repo this adds 30-60s and wastes disk."
        ),
        scope=[
            "Replace `prepare_sandbox` clone with a per-run `git worktree add` against a long-lived bare clone in `data/repos/<project_id>.git`.",
            "Bare clone is created on first project use and refreshed before each run with `git fetch`.",
            "Run cleanup removes the worktree but keeps the bare clone.",
        ],
        tech=[
            "Edit `apps/api/ouroboros_api/sandbox/workspace.py:prepare_sandbox`.",
            "Add `RepoCache` helper for the bare clones.",
            "Migration not needed; existing `data/runs/<id>/repo` paths still work as worktree targets.",
        ],
        accept=[
            "Second run on the same project starts in <2s (vs ~30s) on a 1GB repo.",
            "Concurrent runs on the same project do not corrupt each other (each gets its own worktree).",
            "Deleting a project removes its bare clone.",
        ],
        parallel="Pairs naturally with TBD-13 (concurrency); both want fast sandbox prep.",
    ),
    Ticket(
        key="TBD-18",
        stage="stage-2",
        tier="Post-MVP",
        title="Local artifact storage GC (LRU eviction)",
        problem=(
            "`data/runs/` grows forever. Long-running installs blow out disk."
        ),
        scope=[
            "Background sweeper: when total size of `data/runs/` exceeds `max_artifact_gb` (default 10), evict oldest succeeded runs first.",
            "Failed runs are preserved twice as long as succeeded ones.",
            "Eviction logged to `data/logs/gc.jsonl`.",
        ],
        tech=[
            "New module `apps/api/ouroboros_api/maintenance/gc.py` running on a 5-min asyncio interval.",
            "Tracks size via `os.statvfs` + cached recursive size per run.",
            "Setting `OUROBOROS_MAX_ARTIFACT_GB` (default 10).",
        ],
        accept=[
            "Filling `data/runs/` past the cap deletes the oldest succeeded run within one sweep.",
            "Run rows are kept (only the on-disk artifacts are evicted; `Run.has_artifacts` flips to false).",
            "Disabling via `OUROBOROS_MAX_ARTIFACT_GB=0` halts the sweeper.",
        ],
        parallel="Independent.",
    ),
    Ticket(
        key="TBD-19",
        stage="stage-2",
        tier="Post-MVP",
        title="Provider failover: 5xx on Anthropic -> retry on Ollama equivalent",
        problem=(
            "A flaky upstream brings the whole run down. The engine retries the same step but "
            "always hits the same broken provider."
        ),
        scope=[
            "Per-agent `model_policy.failover` list: ordered list of `(provider_kind, model_hint)` to try after the primary.",
            "On 5xx / connection-reset / timeout, the engine moves to the next failover entry without bumping `attempt`.",
            "Failovers are recorded as artifacts so the user can see why a different model ran.",
        ],
        tech=[
            "Edit `apps/api/ouroboros_api/orchestrator/engine.py:_dispatch_node` to catch retryable upstream errors.",
            "Edit `apps/api/ouroboros_api/orchestrator/router.py` to expose a `pick_failover` helper.",
            "Frontend: add a `Failover` editor on the agent page next to the policy editor.",
        ],
        accept=[
            "Disabling Anthropic mid-run lets the next step land on Ollama without user intervention.",
            "Failover events surface in the run plan with a banner on affected steps.",
            "Without a configured failover list the engine falls back to the existing retry behaviour (no regression).",
        ],
        parallel="After TBD-04 / TBD-11. Touches `engine.py` so coordinate with TBD-07 (resume).",
        deps=["TBD-04"],
    ),
    Ticket(
        key="TBD-20",
        stage="stage-2",
        tier="Post-MVP",
        title="First-class GitLab parity: MR comments, pipeline links, body markdown",
        problem=(
            "GitLab works but is a second-class citizen: no MR comments, pipelines invisible, "
            "issue bodies not always rendered."
        ),
        scope=[
            "Implement `GitlabClient.comment_on_mr`, `.create_mr`, `.fetch_pipeline_status`.",
            "Issues page renders GitLab markdown with the same react-markdown stack as GitHub.",
            "Run summary surfaces the MR + pipeline URL after a successful push.",
        ],
        tech=[
            "Edit `apps/api/ouroboros_api/scm/gitlab.py`.",
            "Add `glab` CLI fallback if available; otherwise REST.",
            "No frontend schema change beyond adding pipeline URL to the run detail.",
        ],
        accept=[
            "Running an MVP flow against a GitLab project leaves a comment on the MR.",
            "Pipeline status appears live on the run detail page.",
            "GitLab markdown including emoji and tables renders correctly.",
        ],
        parallel="Independent.",
    ),
    Ticket(
        key="TBD-21",
        stage="stage-2",
        tier="Post-MVP",
        title="Bitbucket Cloud + Bitbucket DC adapter",
        problem=(
            "Bitbucket is widely used in regulated shops. Today Ouroboros has no path to "
            "support them, blocking those design partners."
        ),
        scope=[
            "New `BitbucketCloudClient` and `BitbucketDcClient` implementing `ScmClient`.",
            "PR + issue + repo introspection parity with GitHub adapter.",
            "OAuth 2.0 + app passwords supported for Cloud; PAT for DC.",
        ],
        tech=[
            "New `apps/api/ouroboros_api/scm/bitbucket_cloud.py` and `bitbucket_dc.py`.",
            "Extend `Project.scm_kind` enum + Alembic migration.",
            "Frontend: SCM dropdown adds the two options.",
        ],
        accept=[
            "Cloud project: full /implement run completes.",
            "DC project: same against an on-prem Bitbucket instance.",
            "Existing GitHub + GitLab paths untouched (regression suite passes).",
        ],
        parallel="Independent. Pairs with TBD-20 (parity work).",
    ),
    Ticket(
        key="TBD-22",
        stage="stage-2",
        tier="Post-MVP",
        title="Roadmap-aware planner: feed paired roadmap entry into the prompt",
        problem=(
            "We already match issues to roadmap entries but never pass the entry into the "
            "planner. The planner therefore re-discovers context that already exists in the repo."
        ),
        scope=[
            "When a run has paired `IssueRoadmapPair` rows, render their titles + bodies into the planner system prompt.",
            "Cap at 2k tokens; truncate longest first.",
            "Audit log records which entries were used.",
        ],
        tech=[
            "Edit the planner agent's prompt assembly to query `IssueRoadmapPair`.",
            "No schema changes.",
        ],
        accept=[
            "A run on a paired issue shows the roadmap titles in the planner's system-prompt artifact.",
            "Unpaired issues run unchanged.",
            "Token cap is respected (verified by a unit test).",
        ],
        parallel="Independent.",
    ),
    Ticket(
        key="TBD-23",
        stage="stage-2",
        tier="Post-MVP",
        title="Inline MCP tool inspector on the run detail page",
        problem=(
            "When an agent calls an MCP tool, the only record is a generic `tool_call` artifact. "
            "Hard to debug malformed args or unexpected outputs."
        ),
        scope=[
            "Right-side pane on the run detail page that lists every MCP tool call as it happens.",
            "Each entry: server name, tool name, args (collapsible JSON), output (collapsible JSON), latency.",
            "Click-through to the corresponding step.",
        ],
        tech=[
            "Backend already records `mcp.tool_call` artifacts; surface them via an existing endpoint.",
            "New component `apps/web/src/components/runs/mcp-inspector.tsx`.",
        ],
        accept=[
            "Calling an MCP tool during a run shows up in the inspector within 1s.",
            "Filtering by server name works.",
            "Empty state hides the pane entirely.",
        ],
        parallel="Independent.",
    ),
    Ticket(
        key="TBD-24",
        stage="stage-2",
        tier="Post-MVP",
        title="Replay mode: re-run a single failed step against a different model",
        problem=(
            "When a single step fails, the user has to retry the whole run, paying for and "
            "re-doing all the prior steps."
        ),
        scope=[
            "On a failed step in run detail: `Replay with...` action -> picks a different provider/model.",
            "Engine re-runs only that step using the persisted prior context.",
            "If replay succeeds, downstream steps continue from there.",
        ],
        tech=[
            "Reuses TBD-07 snapshot infrastructure.",
            "New endpoint `POST /api/runs/{id}/steps/{step_id}/replay {provider_id, model_id}`.",
            "Frontend: dropdown on each failed step row.",
        ],
        accept=[
            "Replaying a failed step does not re-execute earlier successful steps.",
            "The replay records a fresh `RunStep` with `attempt=N+1` and the chosen model.",
            "Downstream steps then run as usual.",
        ],
        parallel="Strict dep on TBD-07.",
        deps=["TBD-07"],
    ),
    Ticket(
        key="TBD-25",
        stage="stage-2",
        tier="Post-MVP",
        title="Save-as-flow: convert a successful run into a reusable Flow template",
        problem=(
            "Today users design flows on the routing page but rarely capture what an actual "
            "successful run looked like as a reusable template."
        ),
        scope=[
            "On any succeeded run: `Save as Flow` action prompts for a name.",
            "Resulting Flow has the same node/edge layout, the same agent assignments, and the same model overrides.",
            "Flagged as `derived_from_run_id` for provenance.",
        ],
        tech=[
            "Add `Flow.derived_from_run_id` column.",
            "Endpoint `POST /api/runs/{id}/save-as-flow {name}`.",
            "Engine runs against derived flows just like designed flows.",
        ],
        accept=[
            "Saving from a 7-step run creates a Flow with 7 nodes and identical edges.",
            "The new Flow shows up in the routing page sidebar with a `derived` badge.",
            "Editing the derived Flow does not affect the source run.",
        ],
        parallel="Independent.",
    ),

    # ----- STAGE 3: Quality, observability, operability (9 tickets) -----
    Ticket(
        key="TBD-26",
        stage="stage-3",
        tier="Post-MVP",
        title="Structured JSON event log to file rotation in `data/logs/`",
        problem=(
            "Today engine logs go to stderr only. Cloud and Enterprise need durable, queryable "
            "logs with rotation."
        ),
        scope=[
            "Configure `structlog` to emit JSON to `data/logs/ouroboros.jsonl`.",
            "Daily rotation with 14-day retention (configurable).",
            "Each event includes `workspace_id`, `run_id`, `step_id`, `agent_id` where present.",
        ],
        tech=[
            "Add `structlog` JSONRenderer + a `RotatingFileHandler`.",
            "Wire from `apps/api/ouroboros_api/main.py:lifespan`.",
            "Settings: `OUROBOROS_LOG_DIR`, `OUROBOROS_LOG_RETENTION_DAYS`.",
        ],
        accept=[
            "All run + step events appear in the file within 1s.",
            "Rotation creates `ouroboros-YYYY-MM-DD.jsonl` daily and deletes anything older than retention.",
            "stderr output remains for dev convenience.",
        ],
        parallel="Independent. Foundation for TBD-27/28/41.",
    ),
    Ticket(
        key="TBD-27",
        stage="stage-3",
        tier="Post-MVP",
        title="Prometheus `/metrics` endpoint",
        problem=(
            "Hosted Ouroboros needs first-class metrics: run rates, token spend, intervention "
            "age, MCP failure rate, queue depth."
        ),
        scope=[
            "Mount `/metrics` returning Prometheus text format.",
            "Counters: `ouroboros_runs_total`, `ouroboros_steps_total{status}`, `ouroboros_tokens_total{provider,kind}`.",
            "Gauges: `ouroboros_runs_running`, `ouroboros_intervention_pending_seconds`.",
        ],
        tech=[
            "Use `prometheus-client`.",
            "Instrument inside `RunEngine` and `RunEventBus`.",
            "New router `apps/api/ouroboros_api/api/metrics.py`.",
        ],
        accept=[
            "`curl /metrics` returns valid Prometheus exposition.",
            "All counters/gauges have HELP and TYPE lines.",
            "Auth-gateable via `OUROBOROS_METRICS_TOKEN` (optional bearer).",
        ],
        parallel="Independent.",
    ),
    Ticket(
        key="TBD-28",
        stage="stage-3",
        tier="Post-MVP",
        title="OpenTelemetry tracing for each agent step",
        problem=(
            "Cross-service tracing is the only way to debug 90s latency mysteries in a multi-"
            "provider, multi-MCP run."
        ),
        scope=[
            "Each `RunStep` opens an OTel span; child spans for each tool call and provider request.",
            "OTLP HTTP exporter; configurable endpoint via env.",
            "Span attributes include provider, model, tokens, dry-run flag.",
        ],
        tech=[
            "Add `opentelemetry-sdk` + `opentelemetry-instrumentation-fastapi`.",
            "New module `apps/api/ouroboros_api/observability/tracing.py`.",
            "Wire via FastAPI middleware + manual spans inside engine.",
        ],
        accept=[
            "Spans visible in a local Jaeger via OTLP within 1s of step finish.",
            "Disabling via `OTEL_SDK_DISABLED=true` removes overhead entirely.",
            "Adapters opt into custom span attributes with no global coupling.",
        ],
        parallel="Pairs with TBD-27.",
    ),
    Ticket(
        key="TBD-29",
        stage="stage-3",
        tier="Post-MVP",
        title="Backup + restore CLI (`ouroboros backup` / `ouroboros restore`)",
        problem=(
            "Local installs accumulate valuable run history. There is no documented backup "
            "story today; lose the laptop, lose the state."
        ),
        scope=[
            "`ouroboros backup [path]` writes a `.tar.zst` of `data/ouroboros.sqlite` + `data/runs/` + `data/logs/`.",
            "`ouroboros restore <path>` does the inverse, refusing if the target dir is non-empty.",
            "Optional `--exclude-artifacts` flag for small backups.",
        ],
        tech=[
            "Extends the CLI from TBD-06.",
            "Uses `tarfile` + `zstandard`.",
            "Backup is hot (SQLite WAL mode) + verifies via `PRAGMA integrity_check`.",
        ],
        accept=[
            "Backup of a 5GB run history completes in <60s.",
            "Restore on a clean directory recreates a working install.",
            "Refusing to restore over a non-empty data dir prints a clear error.",
        ],
        parallel="After TBD-06 (CLI scaffolding).",
        deps=["TBD-06"],
    ),
    Ticket(
        key="TBD-30",
        stage="stage-3",
        tier="Post-MVP",
        title="One-command SQLite -> Postgres migration",
        problem=(
            "First step toward Cloud Solo. Migrating a non-trivial SQLite is enough friction "
            "to lose a customer."
        ),
        scope=[
            "`ouroboros migrate-to-postgres <postgres-url>` reads SQLite tables, applies Alembic on Postgres, and copies row by row.",
            "Verifies row counts post-copy.",
            "Source SQLite is preserved untouched.",
        ],
        tech=[
            "Extends the CLI; uses SQLAlchemy core for streaming inserts.",
            "Smoke test runs against a docker-compose Postgres in CI.",
        ],
        accept=[
            "Migrating a 100k-row install completes in <5min.",
            "Row count + checksum per table match before/after.",
            "Engine starts cleanly against the new Postgres URL.",
        ],
        parallel="Independent. Critical path for Stage 4.",
    ),
    Ticket(
        key="TBD-31",
        stage="stage-3",
        tier="Post-MVP",
        title="Fuzz tests for `classify_command`",
        problem=(
            "Dry-run safety hinges on correctly classifying side-effecting shell commands. A "
            "missed pattern silently exfiltrates work."
        ),
        scope=[
            "`hypothesis`-driven fuzz that generates random shell commands (with prefixes, env vars, redirects).",
            "Asserts: no command containing `git push`, `gh pr create`, `npm publish` etc. is ever classified non-`side_effect`.",
            "Runs in CI on every PR.",
        ],
        tech=[
            "Extend `apps/api/tests/test_dry_run.py`.",
            "Generators in `apps/api/tests/strategies.py`.",
        ],
        accept=[
            "A regression of `classify_command` is caught by the fuzz suite within 100 examples.",
            "CI run takes <30s.",
            "False positives (e.g. mentioning `git push` inside an echo'd string) are documented.",
        ],
        parallel="Independent.",
    ),
    Ticket(
        key="TBD-32",
        stage="stage-3",
        tier="Post-MVP",
        title="Adversarial prompt-injection test pack against the sandbox",
        problem=(
            "An issue body is untrusted input. We need to prove that prompt injection cannot "
            "exfiltrate data, push code, or escape the sandbox."
        ),
        scope=[
            "Curated set of 30+ adversarial issue bodies (encoded URLs, system-prompt-overrides, MCP-tool-spoofs).",
            "Run weekly against a fixture flow + mock provider that replays the injection.",
            "Test fails if any side-effecting command is observed.",
        ],
        tech=[
            "New `apps/api/tests/adversarial/` directory.",
            "GitHub Actions weekly cron + on-demand workflow_dispatch.",
        ],
        accept=[
            "All 30 attacks fail to produce a side-effecting command.",
            "Failures are reported in the workflow with the offending command captured.",
            "Adding a new attack is one PR.",
        ],
        parallel="Independent.",
    ),
    Ticket(
        key="TBD-33",
        stage="stage-3",
        tier="Post-MVP",
        title="Provider rate-limit-aware backpressure (429 -> exponential pause)",
        problem=(
            "Hitting an Anthropic 429 today fails the step. We should pause and resume."
        ),
        scope=[
            "On HTTP 429 + `Retry-After` header, the engine sleeps for the prescribed time then retries the same step.",
            "Without `Retry-After`, exponential backoff up to 60s.",
            "Surface as `step.paused` events on the WebSocket.",
        ],
        tech=[
            "Edit each LLM provider to raise a typed `RateLimited(retry_after)` exception.",
            "Engine catches it and schedules the resume.",
        ],
        accept=[
            "Simulated 429 against Anthropic mock pauses then succeeds without bumping `attempt`.",
            "Cancelling during pause aborts cleanly.",
            "Backoff cap honoured.",
        ],
        parallel="Pairs with TBD-13 (concurrency).",
    ),
    Ticket(
        key="TBD-34",
        stage="stage-3",
        tier="Post-MVP",
        title="Configurable model price catalog (`provider_prices.yaml`)",
        problem=(
            "Provider pricing changes monthly. We currently rely on what the provider returns "
            "in its catalog, which is often missing or stale."
        ),
        scope=[
            "Optional `data/provider_prices.yaml` keyed by `(provider_kind, model_id)` with `input_per_mtok` / `output_per_mtok`.",
            "Loaded on boot and on file change (watchfiles).",
            "Wins over provider-supplied pricing.",
        ],
        tech=[
            "New module `apps/api/ouroboros_api/services/price_catalog.py`.",
            "Hooked into `apps/api/ouroboros_api/orchestrator/cost.py:estimate_cost_usd` resolution.",
            "Schema: validated via pydantic.",
        ],
        accept=[
            "Editing the YAML changes cost displays without a restart.",
            "Catalog parse errors surface in the Provider page.",
            "An empty/missing file is a no-op (existing behaviour preserved).",
        ],
        parallel="Pairs with TBD-10 / TBD-58.",
    ),

    # ----- STAGE 4: Cloud (9 tickets, all Cloud) -----
    Ticket(
        key="TBD-35",
        stage="stage-4",
        tier="Cloud",
        title="Auth: GitHub OAuth + email magic link",
        problem=(
            "Cloud cannot exist without authenticated users. OAuth + magic link covers "
            "developers and non-GitHub users (data eng, PMs)."
        ),
        scope=[
            "GitHub OAuth (`read:user`, `read:org`, `repo` for SCM operations).",
            "Email magic link via Resend or Postmark (configurable).",
            "Session cookie + JWT access token model.",
        ],
        tech=[
            "Lives in private `ouroboros-cloud` package; OSS exposes a pluggable `AuthBackend` interface.",
            "Adds `User`, `Session`, `WorkspaceMembership` tables (private side).",
            "Frontend: new `/login` page, redirect-aware.",
        ],
        accept=[
            "Sign-in with GitHub creates a workspace if first user.",
            "Magic link succeeds within the email TTL (15 min default).",
            "Logout invalidates the session cookie + JWT both.",
        ],
        parallel="Critical path for everything Cloud.",
    ),
    Ticket(
        key="TBD-36",
        stage="stage-4",
        tier="Cloud",
        title="Workspace invites + RBAC (owner / maintainer / runner / viewer)",
        problem=(
            "Multi-user workspaces need permissions: a viewer must not be able to start runs, "
            "a runner must not be able to delete projects."
        ),
        scope=[
            "Four roles enforced on every router.",
            "Invite by email; new user gets the workspace at the assigned role.",
            "Audit log records role changes.",
        ],
        tech=[
            "New decorator `@requires_role('maintainer')` on FastAPI routes.",
            "Frontend: `/workspace/members` page; sidebar gates by role.",
            "Migration: `WorkspaceMembership.role` enum.",
        ],
        accept=[
            "Demoting a user to viewer mid-session causes their next mutating request to 403.",
            "Owner cannot remove themselves if last owner.",
            "Invites expire after 7 days.",
        ],
        parallel="Strict dep on TBD-35.",
        deps=["TBD-35"],
    ),
    Ticket(
        key="TBD-37",
        stage="stage-4",
        tier="Cloud",
        title="Org-shared providers (admin sets key; runner consumes; key never leaves server)",
        problem=(
            "On Cloud Team, the workspace owner pays for managed model usage. We must let them "
            "set a key once and never expose it to runners."
        ),
        scope=[
            "Admin sets the API key via the Provider page.",
            "Runners can use the provider but cannot read or export the key.",
            "Backed by `SecretsBackend(VaultBackend)` in cloud, so the API process never holds plaintext keys at rest.",
        ],
        tech=[
            "Add `Provider.shared_org_wide` flag.",
            "Edit `apps/api/ouroboros_api/api/providers.py` to redact `api_key` from responses for non-owners.",
            "Add `VaultBackend` (private package).",
        ],
        accept=[
            "Runner GET /providers/{id} returns `has_api_key=true` but no `api_key`.",
            "Runner can launch a run that uses the shared provider.",
            "Owner can rotate the key without breaking running tasks (next request uses new key).",
        ],
        parallel="After TBD-35/TBD-36.",
        deps=["TBD-36"],
    ),
    Ticket(
        key="TBD-38",
        stage="stage-4",
        tier="Cloud",
        title="Stripe metered billing (RunMeter aggregator + nightly reconcile)",
        problem=(
            "Cloud needs to bill. The metering formula in `BUSINESS_MODEL.md` is defined; we "
            "must implement and reconcile it."
        ),
        scope=[
            "New `RunMeter` table with the columns described in BUSINESS_MODEL.md \u00a73.",
            "Engine writes a meter row at run completion.",
            "Nightly job aggregates and posts `usage_record` to Stripe per `SubscriptionItem`.",
        ],
        tech=[
            "Private `ouroboros-cloud` package owns the Stripe SDK calls.",
            "Webhook router for `customer.subscription.deleted` etc.",
            "Idempotency key per usage post.",
        ],
        accept=[
            "A test workspace running 10 runs has correct `tokens_in_managed`, `tokens_out_managed`, `concurrent_slots` posted in 24h.",
            "Subscription cancellation triggers grace + downgrade.",
            "Reconciliation against Stripe invoice differs by <0.1%.",
        ],
        parallel="After TBD-35.",
        deps=["TBD-35"],
    ),
    Ticket(
        key="TBD-39",
        stage="stage-4",
        tier="Cloud",
        title="Managed-models proxy (resell Anthropic/OpenAI/Bedrock with caching)",
        problem=(
            "Customers who do not want to manage provider keys should buy bundled inference "
            "from us at a transparent markup."
        ),
        scope=[
            "Outbound proxy in `ouroboros-cloud` that holds our master keys, multiplexes per-tenant requests, applies markup, and emits billing events.",
            "Hard monthly spend cap per workspace.",
            "Optional response caching on identical (model, prompt) tuples for 24h.",
        ],
        tech=[
            "New private service; OSS exposes a `provider_kind=ouroboros_managed` so the engine can target it.",
            "`MetricsCollector` instrumented for per-tenant cost.",
        ],
        accept=[
            "Enabling managed models on a workspace lets runs use `ouroboros_managed:claude-3-5-sonnet`.",
            "Hitting the spend cap pauses further runs with a clear error.",
            "Cache hits are billed at 25% of base cost.",
        ],
        parallel="After TBD-37/TBD-38.",
        deps=["TBD-38"],
    ),
    Ticket(
        key="TBD-40",
        stage="stage-4",
        tier="Cloud",
        title="S3-compatible artifact storage backend",
        problem=(
            "Cloud cannot store artifacts on local disk. A pluggable `ArtifactStore` is needed."
        ),
        scope=[
            "`ArtifactStore` abstract base with `LocalDiskStore` (default) and `S3Store` implementations.",
            "Per-workspace bucket prefix; signed URL generation for downloads.",
            "Background migration tool to move existing local artifacts -> S3 on enablement.",
        ],
        tech=[
            "Module `apps/api/ouroboros_api/storage/`.",
            "S3 access via `aioboto3`; works against any S3-compatible endpoint (Wasabi, MinIO, R2).",
            "Settings: `OUROBOROS_ARTIFACT_BACKEND`, `OUROBOROS_S3_*`.",
        ],
        accept=[
            "Switching backend to `s3` writes new artifacts to S3.",
            "Existing local artifacts are accessible via signed URL after migration.",
            "Local backend remains the default (no behaviour change for OSS users).",
        ],
        parallel="Independent of other Stage 4 tickets.",
    ),
    Ticket(
        key="TBD-41",
        stage="stage-4",
        tier="Cloud",
        title="Audit log export to S3/GCS/webhook (daily delivery)",
        problem=(
            "Compliance customers need tamper-evident, exportable audit logs."
        ),
        scope=[
            "Daily packager: yesterday's events from `data/logs/ouroboros.jsonl` -> `audit-YYYY-MM-DD.jsonl.gz` -> upload to configured destination.",
            "Per-workspace destination + format.",
            "Failure to deliver paged via the existing notification system.",
        ],
        tech=[
            "Reuses TBD-26 logs.",
            "Implements `AuditExporter` ABC with `S3Exporter`, `GCSExporter`, `WebhookExporter`.",
            "Cron via APScheduler.",
        ],
        accept=[
            "Configured destination receives the prior day's bundle within 1h of UTC midnight.",
            "Bundle SHA256 logged for tamper evidence.",
            "Retries on transient upload failures.",
        ],
        parallel="After TBD-26.",
        deps=["TBD-26"],
    ),
    Ticket(
        key="TBD-42",
        stage="stage-4",
        tier="Cloud",
        title="Webhook delivery for `run.*` events (HMAC-signed, retried)",
        problem=(
            "External systems (CI dashboards, Linear automations) need a stable way to react "
            "to run lifecycle events."
        ),
        scope=[
            "Per-workspace webhook subscriptions with secret + event filter.",
            "HMAC-SHA256 signature in `X-Ouroboros-Signature`.",
            "Retries with jittered exponential backoff up to 24h, then dead-letter.",
        ],
        tech=[
            "Subscribes to `RunEventBus`; new `WebhookDelivery` table.",
            "Worker pool processes the delivery queue.",
            "Frontend: `/webhooks` page in the workspace settings.",
        ],
        accept=[
            "A run.failed event reaches a configured webhook within 5s under happy path.",
            "5xx responses retry; final failure surfaces in the audit log.",
            "Signature validation example documented.",
        ],
        parallel="Pairs with TBD-14 (notifications).",
    ),
    Ticket(
        key="TBD-43",
        stage="stage-4",
        tier="Cloud",
        title="Public REST API tokens with per-token rate limiting",
        problem=(
            "Programmatic CI integrations need stable tokens distinct from user sessions."
        ),
        scope=[
            "`/settings/api-tokens` page to mint + revoke tokens.",
            "Each token has scope (`read`, `runs:start`, `admin`) + rate limit (default 1000 req/h).",
            "Audit log captures token id on every request.",
        ],
        tech=[
            "New `ApiToken` table; bearer-token middleware short-circuits the session machinery.",
            "Rate limit via Redis token bucket (Cloud) or in-memory (OSS).",
        ],
        accept=[
            "Minted token used in a curl POST to `/api/runs` succeeds within scope.",
            "Exceeding the rate limit returns 429 with `Retry-After`.",
            "Revoked token returns 401 within 60s.",
        ],
        parallel="After TBD-35.",
        deps=["TBD-35"],
    ),

    # ----- STAGE 5: Enterprise (12 tickets, all Enterprise) -----
    Ticket(
        key="TBD-44",
        stage="stage-5",
        tier="Enterprise",
        title="SAML / OIDC SSO with JIT provisioning",
        problem=(
            "Enterprises require SSO via their existing IdP. No SSO = no deal."
        ),
        scope=[
            "SAML 2.0 + OIDC support, configured per workspace.",
            "JIT user creation on first login; role mapped from IdP group claim.",
            "Optional enforced-SSO mode (disable email/password fallback).",
        ],
        tech=[
            "Use `python-social-auth` or `authlib`.",
            "Lives in private `ouroboros-cloud`.",
            "Enterprise admin UI for IdP metadata upload.",
        ],
        accept=[
            "Okta SAML test app provisions a user on first login.",
            "Group claim `ouroboros:owner` -> owner role.",
            "SSO-only mode rejects email login attempts.",
        ],
        parallel="Critical path for Enterprise.",
    ),
    Ticket(
        key="TBD-45",
        stage="stage-5",
        tier="Enterprise",
        title="SCIM 2.0 user/group provisioning",
        problem=(
            "Manual user management at enterprise scale is unworkable. SCIM is the standard."
        ),
        scope=[
            "SCIM 2.0 endpoints for `/Users` and `/Groups`.",
            "Bidirectional sync with Okta + Azure AD test instances.",
            "Deprovision = revoke session + remove from workspaces.",
        ],
        tech=[
            "Implements RFC 7644.",
            "Lives in private `ouroboros-cloud`.",
        ],
        accept=[
            "Okta sync creates 100 users in <60s.",
            "Removing a user in Okta deactivates them in Ouroboros within one sync cycle.",
            "Group changes propagate to workspace memberships.",
        ],
        parallel="After TBD-44.",
        deps=["TBD-44"],
    ),
    Ticket(
        key="TBD-46",
        stage="stage-5",
        tier="Enterprise",
        title="Customer-managed KMS for `SecretsBackend` (BYOK)",
        problem=(
            "Enterprises require customer-controlled encryption keys for secrets at rest."
        ),
        scope=[
            "Backends: AWS KMS, GCP KMS, HashiCorp Vault Transit.",
            "Per-workspace key ARN/URI configuration.",
            "Key rotation triggers re-encryption of stored secrets.",
        ],
        tech=[
            "Implements `SecretsBackend` ABC.",
            "Lives in private `ouroboros-cloud`.",
            "Audit every encrypt/decrypt operation.",
        ],
        accept=[
            "Setting `aws_kms` on a workspace re-encrypts all stored provider keys.",
            "Rotating the key rotates ciphertext without downtime.",
            "Loss of access to KMS surfaces a clear error on every secret read.",
        ],
        parallel="Independent of TBD-44/TBD-45.",
    ),
    Ticket(
        key="TBD-47",
        stage="stage-5",
        tier="Enterprise",
        title="Air-gapped deploy mode (Ollama-only routing enforced)",
        problem=(
            "Some deployments must guarantee zero outbound traffic from agents (defense, gov, "
            "hospital networks)."
        ),
        scope=[
            "Deployment-wide flag `OUROBOROS_AIR_GAPPED=true` that:",
            "  - Refuses to start with any non-Ollama provider configured.",
            "  - Refuses to enable any MCP server with `network=true` capability.",
            "  - Hard-fails any agent step that attempts an outbound connection (egress proxy).",
        ],
        tech=[
            "Boot-time validator + runtime egress monitor.",
            "Optional sidecar `egress-proxy` container that sinkholes everything except whitelisted hostnames.",
        ],
        accept=[
            "Enabled mode + Anthropic provider in DB -> startup error.",
            "Enabled mode + an attempted outbound HTTP call -> step fails with `air-gapped: blocked egress`.",
            "Documentation includes the threat model.",
        ],
        parallel="Independent.",
    ),
    Ticket(
        key="TBD-48",
        stage="stage-5",
        tier="Enterprise",
        title="OPA/Rego policy engine per workspace",
        problem=(
            "Enterprises encode policies declaratively. We need to consume them, not reinvent."
        ),
        scope=[
            "Policy file per workspace evaluated at: flow start, before each side-effecting step.",
            "Policies can deny based on `repo`, `branch`, `agent`, `model`, `time-of-day`.",
            "Denials surface as run cancellations with `policy-denied: <rule-id>`.",
        ],
        tech=[
            "OPA evaluated via `opa-python` SDK or sidecar.",
            "Policy files stored in `Workspace.policy_bundle_url`.",
            "Hot-reload on file change.",
        ],
        accept=[
            "A `deny if branch == 'main'` rule blocks a run targeting main.",
            "Test policy bundle fixture in CI.",
            "Audit log includes the policy decision per evaluation.",
        ],
        parallel="Pairs with TBD-15 (require_approval).",
    ),
    Ticket(
        key="TBD-49",
        stage="stage-5",
        tier="Enterprise",
        title="Data residency selector per workspace",
        problem=(
            "EU and APAC customers require their data physically not leave their region."
        ),
        scope=[
            "Workspace pinned to a region at creation; immutable.",
            "Per-region S3 bucket + Postgres replica.",
            "Provider routing only allows region-local endpoints (Anthropic EU, Bedrock per region, etc.).",
        ],
        tech=[
            "Cloud control plane reads `Workspace.region` and routes API requests to the correct cluster.",
            "Cell-based architecture documented.",
        ],
        accept=[
            "An EU workspace has all artifacts stored in `eu-west-1`.",
            "Attempting to use a US-only model from an EU workspace returns 400 with policy error.",
            "Cross-region data leakage test in CI returns clean.",
        ],
        parallel="Major architecture work; coordinate with TBD-46/TBD-50.",
    ),
    Ticket(
        key="TBD-50",
        stage="stage-5",
        tier="Enterprise",
        title="Customer-managed CA + mTLS between API <-> web <-> MCP",
        problem=(
            "Regulated networks require mutual TLS for internal services."
        ),
        scope=[
            "Configurable client + server certs for: API <-> Web, API <-> MCP servers, API <-> external providers.",
            "Per-workspace truststore.",
            "Cert expiry alerts via the notification system.",
        ],
        tech=[
            "uvicorn + httpx ssl context override.",
            "Helm chart wires cert-manager + customer CA.",
        ],
        accept=[
            "Stand up the helm chart with a self-signed CA -> all internal calls succeed.",
            "Expired cert pages a warning 7 days before expiry.",
            "Provider request with an untrusted cert fails with a clear TLS error.",
        ],
        parallel="After TBD-53 (helm chart).",
        deps=["TBD-53"],
    ),
    Ticket(
        key="TBD-51",
        stage="stage-5",
        tier="Enterprise",
        title="Tamper-evident append-only audit log (Merkle-chained, daily root signed)",
        problem=(
            "SOX and similar regimes require provably-untampered logs."
        ),
        scope=[
            "Each audit event hashed; daily root hash computed and signed (PKCS#11 or KMS).",
            "Verification CLI reconstructs the chain and proves no insertion/removal.",
            "Signed root shipped to the audit export destination (TBD-41).",
        ],
        tech=[
            "Merkle implementation via `pymerkle`.",
            "Signing via the configured KMS (TBD-46).",
            "Verification CLI ships in OSS for transparency.",
        ],
        accept=[
            "Tampering with one log line breaks the verification.",
            "Daily root signature appears in the export bundle.",
            "Verification of 1M-event chain runs in <30s.",
        ],
        parallel="After TBD-26/TBD-41/TBD-46.",
        deps=["TBD-41", "TBD-46"],
    ),
    Ticket(
        key="TBD-52",
        stage="stage-5",
        tier="Enterprise",
        title="Per-data-class retention policies",
        problem=(
            "Different data classes have different legal retention requirements (artifacts 90d, "
            "audit 7y, prompts 0d)."
        ),
        scope=[
            "Configurable per workspace: artifact, audit, prompt, completion retention windows.",
            "Background sweeper enforces policies daily.",
            "Default templates: `gdpr-eu`, `hipaa-us`, `permissive`.",
        ],
        tech=[
            "Extends TBD-18 (artifact GC) with policy-driven retention.",
            "Adds `Workspace.retention_policy_json`.",
        ],
        accept=[
            "Setting `prompt_retention_days=0` causes prompt artifacts to be redacted on write.",
            "Audit retention beyond 7y blocked by default to prevent accidental over-retention.",
            "Policy change recorded in audit log.",
        ],
        parallel="After TBD-18.",
        deps=["TBD-18"],
    ),
    Ticket(
        key="TBD-53",
        stage="stage-5",
        tier="Enterprise",
        title="Helm chart + Terraform module for self-hosted deployment",
        problem=(
            "On-prem customers need a one-command deployment artifact targeting EKS, GKE, AKS, "
            "OpenShift."
        ),
        scope=[
            "Helm chart in `deploy/helm/ouroboros/` covering API, web, Postgres, Redis (optional), Ollama (optional).",
            "Terraform module in `deploy/terraform/aws/` provisioning EKS + RDS + S3.",
            "Documentation for sizing + scaling.",
        ],
        tech=[
            "Lives in the OSS repo (the OSS engine + chart together is the on-prem product).",
            "Includes example `values.yaml` for SSO + KMS + air-gapped.",
        ],
        accept=[
            "`helm install` against a fresh EKS cluster yields a working install.",
            "Terraform `apply` provisions all dependencies.",
            "Documented upgrade path between two versions.",
        ],
        parallel="Critical path for many Stage 5 tickets.",
    ),
    Ticket(
        key="TBD-54",
        stage="stage-5",
        tier="Enterprise",
        title="Customer-managed model gateway (LiteLLM / internal proxy)",
        problem=(
            "Enterprises with their own LLM proxy (LiteLLM, internal) want Ouroboros to route "
            "through it instead of calling Anthropic/OpenAI directly."
        ),
        scope=[
            "New provider kind `customer_gateway` with configurable base URL + auth.",
            "Speaks OpenAI-compatible chat-completions API.",
            "Bypasses the managed-models proxy entirely.",
        ],
        tech=[
            "New `apps/api/ouroboros_api/adapters/providers/customer_gateway.py`.",
            "Reuses the OpenAI-format request/response handling from the GitHub Models adapter.",
        ],
        accept=[
            "Configuring a LiteLLM endpoint and routing the `coder` agent through it succeeds.",
            "Failures from the gateway propagate cleanly.",
            "Catalog of models served by the gateway is fetched via its `/v1/models` endpoint.",
        ],
        parallel="Independent.",
    ),
    Ticket(
        key="TBD-55",
        stage="stage-5",
        tier="Enterprise",
        title="SOC 2 / ISO 27001 evidence collection automation",
        problem=(
            "Quarterly audits eat weeks of engineering time without automation."
        ),
        scope=[
            "Daily snapshot of: access logs, RBAC changes, security-relevant config diffs, vulnerability scan results.",
            "Pushed to an immutable evidence bucket; signed by KMS.",
            "Auditor portal generates packaged evidence per control on demand.",
        ],
        tech=[
            "Lives in private `ouroboros-cloud`.",
            "Reuses TBD-41/TBD-51 export + signing infrastructure.",
        ],
        accept=[
            "Evidence packets cover Trust Services Criteria CC6.* (logical access).",
            "Auditor can self-serve a quarter's evidence in <10min.",
            "Missing snapshots page on-call.",
        ],
        parallel="After TBD-41/TBD-51.",
        deps=["TBD-51"],
    ),

    # ----- STRETCH / RESEARCH (5 tickets) -----
    Ticket(
        key="TBD-56",
        stage="stretch",
        tier="Research",
        title="Self-improving router (logged outcomes -> proposed policy changes)",
        problem=(
            "We collect tokens + cost + outcome per (agent, model) but never close the loop "
            "back to the router policy."
        ),
        scope=[
            "Background analyser proposes policy edits when one model is significantly cheaper "
            "or higher quality for a (language, agent) pair.",
            "Proposals surface in an admin inbox; never auto-applied.",
            "A/B mode optional: 10% of runs use proposed policy, compared.",
        ],
        tech=[
            "Aggregates from `RunStep`.",
            "Proposal table; UI on `/routing/proposals`.",
        ],
        accept=[
            "After 100 runs, at least one well-scoped proposal is generated for the seed flow.",
            "Admin can accept/reject; accepting writes to `Agent.model_policy`.",
            "All proposals are logged for later analysis.",
        ],
        parallel="Independent. Pairs with TBD-58.",
    ),
    Ticket(
        key="TBD-57",
        stage="stretch",
        tier="Research",
        title="`coding-agent benchmark` mode: same issue across N policies, scored by tests",
        problem=(
            "Choosing a policy is guesswork. We can build a head-to-head benchmark out of our "
            "own infra."
        ),
        scope=[
            "New `Benchmark` resource: pick an issue, list of policies to test, success metric (tests pass / build clean / human grade).",
            "Runs all policies in parallel against the issue; aggregates per-policy score.",
            "Output: a leaderboard exportable to JSON / markdown.",
        ],
        tech=[
            "New API + UI surface.",
            "Benchmark engine reuses the existing run engine.",
        ],
        accept=[
            "A benchmark over 3 policies on a fixture issue produces a leaderboard within 1h.",
            "Results are reproducible (same seeds + same providers -> same scores).",
            "Leaderboards persist across runs.",
        ],
        parallel="After TBD-13 (concurrency).",
    ),
    Ticket(
        key="TBD-58",
        stage="stretch",
        tier="Research",
        title="Learned cost predictor (per-repo model improving over time)",
        problem=(
            "TBD-10 forecasts cost via medians. A learned model could be much more accurate."
        ),
        scope=[
            "Train per-(project, agent, model) regressors that predict tokens from issue features (length, label set, files mentioned).",
            "Update online after each run.",
            "Replace TBD-10 forecast endpoint with the predictor when confidence is high.",
        ],
        tech=[
            "scikit-learn linear regression to start; consider gradient boosting later.",
            "Models stored as pickles per project.",
        ],
        accept=[
            "After 50 runs the predictor reduces median absolute error vs the median baseline by >=20%.",
            "Predictor confidence is exposed; low confidence falls back to the baseline.",
            "Retraining runs nightly without blocking the API.",
        ],
        parallel="After TBD-10.",
        deps=["TBD-10"],
    ),
    Ticket(
        key="TBD-59",
        stage="stretch",
        tier="Research",
        title="Local Llama-based review agent that gates merges",
        problem=(
            "Many teams want a final independent reviewer that runs locally (no data leaves the "
            "machine) before any commit lands."
        ),
        scope=[
            "Optional `review.gate` agent in the default flow, configured to run on Ollama.",
            "Reads the diff, scores it on a rubric, blocks the commit step on low scores.",
            "Score threshold + rubric configurable per project.",
        ],
        tech=[
            "Reuses existing Ollama adapter.",
            "Rubric stored as markdown in `Project.review_rubric`.",
        ],
        accept=[
            "A run with a deliberately bad diff is gated by the reviewer.",
            "A clean diff passes.",
            "Disabling the agent skips it entirely.",
        ],
        parallel="Independent.",
    ),
    Ticket(
        key="TBD-60",
        stage="stretch",
        tier="Research",
        title="VS Code / JetBrains plugins to drive Ouroboros runs from inside the IDE",
        problem=(
            "Switching to a browser to launch a run is friction. Many devs would prefer a "
            "right-click in their IDE."
        ),
        scope=[
            "Minimal VS Code extension: pick an issue from the Issues view -> launch a dry-run -> watch live in a webview.",
            "JetBrains plugin: parity for IntelliJ-family IDEs.",
            "Both authenticate via the API token system (TBD-43).",
        ],
        tech=[
            "VS Code: TypeScript, `vscode` API, embeds a webview that loads the existing Next.js run-detail page.",
            "JetBrains: Kotlin, embeds JCEF.",
        ],
        accept=[
            "VS Code extension installs from VSIX and lists workspace projects.",
            "Right-click on a referenced issue number in code -> `Run in Ouroboros`.",
            "Live updates appear in the IDE webview.",
        ],
        parallel="After TBD-43.",
        deps=["TBD-43"],
    ),
]


def assert_ticket_invariants() -> None:
    keys = [t.key for t in TICKETS]
    assert len(keys) == 60, f"expected 60 tickets, got {len(keys)}"
    assert len(set(keys)) == 60, "duplicate ticket keys"
    by_stage: dict[str, int] = {}
    for t in TICKETS:
        by_stage[t.stage] = by_stage.get(t.stage, 0) + 1
    expected = {"stage-1": 8, "stage-2": 17, "stage-3": 9, "stage-4": 9, "stage-5": 12, "stretch": 5}
    assert by_stage == expected, f"counts wrong: {by_stage}"


# ---------------------------------------------------------------------------
# State + gh helpers
# ---------------------------------------------------------------------------


def load_state() -> dict[str, Any]:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {
        "labels": [],
        "milestones": {},
        "epics": {},
        "tickets": {},
    }


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True))


def gh(*args: str, input_data: str | None = None) -> str:
    cmd = ["gh", "-R", REPO, *args]
    out = subprocess.run(
        cmd,
        check=True,
        text=True,
        capture_output=True,
        input=input_data,
    )
    return out.stdout.strip()


def gh_api(method: str, path: str, **fields: Any) -> dict[str, Any]:
    cmd = ["gh", "api", "-X", method, path]
    for k, v in fields.items():
        if isinstance(v, list):
            for item in v:
                cmd.extend(["-f", f"{k}[]={item}"])
        elif isinstance(v, bool):
            cmd.extend(["-F", f"{k}={'true' if v else 'false'}"])
        elif isinstance(v, int):
            cmd.extend(["-F", f"{k}={v}"])
        else:
            cmd.extend(["-f", f"{k}={v}"])
    out = subprocess.run(cmd, check=True, text=True, capture_output=True)
    return json.loads(out.stdout) if out.stdout else {}


# ---------------------------------------------------------------------------
# Body templating
# ---------------------------------------------------------------------------


def render_ticket_body(t: Ticket, epic_number: int) -> str:
    parts: list[str] = []
    parts.append(f"**Epic:** #{epic_number}")
    parts.append(f"**Tier:** `{t.tier}`")
    parts.append(f"**MVP:** {'Yes' if t.tier == 'MVP' else 'No'}")
    parts.append("")
    parts.append("## Problem statement")
    parts.append("")
    parts.append(t.problem)
    parts.append("")
    parts.append("## Solution / scope")
    parts.append("")
    for s in t.scope:
        parts.append(f"- {s}")
    parts.append("")
    parts.append("## Technical specifications")
    parts.append("")
    for s in t.tech:
        parts.append(f"- {s}")
    parts.append("")
    parts.append("## Acceptance criteria")
    parts.append("")
    for s in t.accept:
        parts.append(f"- [ ] {s}")
    parts.append("")
    parts.append("## Parallelism capability")
    parts.append("")
    parts.append(t.parallel)
    if t.deps:
        parts.append("")
        parts.append(f"**Hard dependencies:** {', '.join(t.deps)}")
    parts.append("")
    parts.append("---")
    parts.append("")
    parts.append("*Auto-generated from PLANNED_FEATURE_ROADMAP_2026.md.*")
    return "\n".join(parts)


def render_epic_body(stage: dict[str, Any], children: list[Ticket], child_numbers: dict[str, int]) -> str:
    parts: list[str] = []
    parts.append(f"**Tier:** `{children[0].tier}`")
    parts.append(f"**MVP:** {'Yes' if any(c.tier == 'MVP' for c in children) else 'No'}")
    parts.append("")
    parts.append("## Problem statement")
    parts.append("")
    parts.append(stage["summary"])
    parts.append("")
    parts.append("## Solution / scope")
    parts.append("")
    parts.append("This epic groups the tickets listed below. See each child issue for its")
    parts.append("own problem statement, technical scope, acceptance criteria, and")
    parts.append("parallelism notes.")
    parts.append("")
    parts.append("## Technical specifications")
    parts.append("")
    parts.append("Per-child. The epic itself has no implementation surface.")
    parts.append("")
    parts.append("## Acceptance criteria")
    parts.append("")
    parts.append(f"- [ ] {stage['outcome']}")
    parts.append("- [ ] All child issues below are closed.")
    parts.append("")
    parts.append("## Parallelism capability")
    parts.append("")
    parts.append(
        "Children within this epic can largely be picked up in parallel. Hard "
        "dependencies are noted on each child issue."
    )
    parts.append("")
    parts.append("## Children")
    parts.append("")
    for c in children:
        num = child_numbers.get(c.key)
        prefix = "- [ ]"
        if num:
            parts.append(f"{prefix} #{num} - {c.title}")
        else:
            parts.append(f"{prefix} **(pending)** {c.title}  ({c.key})")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------


def ensure_labels(state: dict[str, Any]) -> None:
    have = set(state.get("labels", []))
    for name, color, desc in LABELS:
        if name in have:
            continue
        try:
            gh("label", "create", name, "--color", color, "--description", desc)
            print(f"  + label {name}")
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr or ""
            if "already exists" in stderr:
                print(f"  = label {name} (existed)")
            else:
                print(f"  ! label {name} failed: {stderr.strip()}")
                raise
        have.add(name)
    state["labels"] = sorted(have)
    save_state(state)


def ensure_milestones(state: dict[str, Any]) -> None:
    existing = state.get("milestones", {})
    for stage in STAGES:
        title = stage["milestone"]
        if title in existing:
            continue
        result = gh_api(
            "POST",
            f"repos/{REPO}/milestones",
            title=title,
            description=stage["summary"],
        )
        existing[title] = result["number"]
        print(f"  + milestone {title} -> #{result['number']}")
    state["milestones"] = existing
    save_state(state)


def ensure_epics(state: dict[str, Any]) -> None:
    epics = state.get("epics", {})
    children_by_stage: dict[str, list[Ticket]] = {s["key"]: [] for s in STAGES}
    for t in TICKETS:
        children_by_stage[t.stage].append(t)

    for stage in STAGES:
        if stage["key"] in epics:
            continue
        children = children_by_stage[stage["key"]]
        body = render_epic_body(stage, children, child_numbers={})
        result = gh_api(
            "POST",
            f"repos/{REPO}/issues",
            title=stage["epic_title"],
            body=body,
            labels=["type:epic", stage["stage_label"]],
            milestone=state["milestones"][stage["milestone"]],
        )
        epics[stage["key"]] = result["number"]
        print(f"  + epic {stage['epic_title']} -> #{result['number']}")
        time.sleep(0.4)
    state["epics"] = epics
    save_state(state)


def ensure_tickets(state: dict[str, Any]) -> None:
    tickets_state: dict[str, int] = state.get("tickets", {})
    for t in TICKETS:
        if t.key in tickets_state:
            continue
        stage = next(s for s in STAGES if s["key"] == t.stage)
        epic_number = state["epics"][t.stage]
        body = render_ticket_body(t, epic_number=epic_number)
        tier_label = {
            "MVP": "tier:mvp",
            "Post-MVP": "tier:post-mvp",
            "Cloud": "tier:cloud",
            "Enterprise": "tier:enterprise",
            "Research": "tier:research",
        }[t.tier]
        result = gh_api(
            "POST",
            f"repos/{REPO}/issues",
            title=t.title,
            body=body,
            labels=[tier_label, stage["stage_label"]],
            milestone=state["milestones"][stage["milestone"]],
        )
        tickets_state[t.key] = result["number"]
        print(f"  + {t.key} -> #{result['number']} ({t.title[:60]})")
        # Save after each ticket so a crash mid-run doesn't lose state.
        state["tickets"] = tickets_state
        save_state(state)
        time.sleep(0.3)


def update_epic_checklists(state: dict[str, Any]) -> None:
    children_by_stage: dict[str, list[Ticket]] = {s["key"]: [] for s in STAGES}
    for t in TICKETS:
        children_by_stage[t.stage].append(t)
    for stage in STAGES:
        epic_num = state["epics"][stage["key"]]
        children = children_by_stage[stage["key"]]
        child_numbers = {c.key: state["tickets"][c.key] for c in children if c.key in state["tickets"]}
        body = render_epic_body(stage, children, child_numbers)
        gh_api("PATCH", f"repos/{REPO}/issues/{epic_num}", body=body)
        print(f"  ~ updated epic #{epic_num} with {len(child_numbers)} child links")


def rewrite_roadmap(state: dict[str, Any]) -> None:
    text = ROADMAP.read_text()
    tickets_state: dict[str, int] = state["tickets"]
    epics: dict[str, int] = state["epics"]
    out = text
    for key, num in tickets_state.items():
        out = re.sub(rf"\b{re.escape(key)}\b", f"#{num}", out)

    epic_lines = ["", "## Epics", ""]
    epic_titles = {s["key"]: s["epic_title"].replace("Epic: ", "") for s in STAGES}
    for stage_key, epic_num in epics.items():
        epic_lines.append(f"- #{epic_num} - {epic_titles.get(stage_key, stage_key)}")
    epic_lines.append("")

    if "## Epics" not in out:
        marker_match = re.search(r"^## Stage 1 [-\u2014] MVP", out, re.MULTILINE)
        if marker_match:
            insert_at = marker_match.start()
            out = out[:insert_at] + "\n".join(epic_lines) + out[insert_at:]

    ROADMAP.write_text(out)
    print(f"  ~ rewrote {ROADMAP.name}: replaced {len(tickets_state)} placeholders")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rewrite", action="store_true", help="Only rewrite the roadmap (assumes state file exists)")
    args = parser.parse_args()

    assert_ticket_invariants()
    state = load_state()

    if args.rewrite:
        rewrite_roadmap(state)
        return 0

    print("== labels ==")
    ensure_labels(state)
    print("== milestones ==")
    ensure_milestones(state)
    print("== epics ==")
    ensure_epics(state)
    print("== tickets ==")
    ensure_tickets(state)
    print("== epic checklists ==")
    update_epic_checklists(state)
    print("== roadmap rewrite ==")
    rewrite_roadmap(state)
    print("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
