# Changelog

## 2026-04-21

- Updated layout and look/feel of the application, far superior than previously designed.
- Added required user accounts and per-workspace RBAC. First run now bootstraps an admin via `/setup`; every API route and WebSocket connection is gated by `current_user` and (where relevant) `require_admin`. Sessions are opaque tokens stored server-side in SQLite and delivered as `HttpOnly`, `SameSite=Lax` cookies with a 30-day sliding expiry.
- Added email/password login, GitHub OAuth (`/api/auth/oauth/github/start`), and self-service registration when `OUROBOROS_AUTH_OPEN_REGISTRATION=true`.
- Added admin user management at `/admin/users` (list, invite, change role, deactivate, remove) with safeguards against demoting or removing the last admin of a workspace.
- Added an account page at `/account` for changing your password and reviewing linked accounts and workspace roles.
- Hid admin-only navigation (Agents, Providers, MCP, Routing) for members; admin-only pages render an "Admins only" placeholder for non-admins.
- Added a minimal `apps/cli/` (`ouroboros login|logout|whoami`) that stores a long-lived API token in the OS keyring and authenticates with `Authorization: Bearer ...`.
- Added multi-server support to the web client. Login and setup pages now show a server picker (Local by default; users can add remote Ouroboros servers by URL). Selection is persisted to `localStorage` and mirrored to an `ob_server` cookie. A new Next route handler at `app/api/[...path]/route.ts` reads the cookie and proxies every API request to the selected backend so session cookies stay first-party. The topbar shows the active server with a one-click switcher that signs the user out and bounces them to the new server's login page. This is the foundation for hosted multi-tenant deployments and customer-managed model/server farms.

## 2026-04-20

- Displays version ID in the upper left-hand corner near the app name.
- Adds support for OpenAI models.
- Fetching and syncing issues now shows a progress bar to show the issues being syncronized in real time.
- Adds the ability to clear run records.
- Adds the ability to test a repository URL when entering it into the projects form.
- Adds project repository tokens for private repository access.
- Adds react-flow styling, hover over edges now shows details between the nodes.
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
