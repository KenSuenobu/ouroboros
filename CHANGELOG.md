# Changelog

## 2026-04-20

- Adds sort order in the issues list.
- Fixes tests and build process.
- Fixes the react-markdown formatting in issues, which was not rendering properly.
- Added true Monaco `DiffEditor` dry-run file diffs using sandbox originals and artifact proposed content, with a per-view side-by-side/unified toggle.
- Added `GET /api/runs/{id}/sandbox-file?path=...` with sandbox path traversal protection and tests for both valid reads and `../../etc/passwd` rejection.

## 2026-04-19

- Added interrupted run recovery with persisted `Run.snapshot_json` context, startup `running -> interrupted` sweep, and a resume API/UI path that skips previously succeeded nodes.
- Added an `ouroboros init` CLI command that prompts for data directory/DB URL and writes `.env` plus `.env.example` without overwriting existing `.env`.
- Added README quick-start Step 0 guidance for running `uv run ouroboros init` before local development setup.
- Added line-by-line shell output streaming via `step.log` run events and surfaced live per-step log panes on the run detail timeline.
- Added shell runner cancellation handling to terminate in-flight subprocesses when runs are cancelled.
- Added per-language router policy defaults to `issue.summarizer`, `planner`, and `internal.audit` seed agents, matching existing `coder` behavior.
- Added migration `0004_seed_agent_router_language_hints` to backfill missing `language_map` hints on seeded router agents.
- Added project repo introspection (`/api/projects/{id}/introspect`) to detect build/test command candidates from common manifests.
- Added one-click command suggestion chips in the Projects UI for build and test fields.
