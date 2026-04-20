# Changelog

## 2026-04-19

- Added per-language router policy defaults to `issue.summarizer`, `planner`, and `internal.audit` seed agents, matching existing `coder` behavior.
- Added migration `0004_seed_agent_router_language_hints` to backfill missing `language_map` hints on seeded router agents.
- Added project repo introspection (`/api/projects/{id}/introspect`) to detect build/test command candidates from common manifests.
- Added one-click command suggestion chips in the Projects UI for build and test fields.
