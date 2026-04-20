# What's New

- Added `ouroboros init` to scaffold `.env` and `.env.example` with default `OUROBOROS_DATA_DIR` and `OUROBOROS_DB_URL` values for first-run setup.
- Added real-time shell step log streaming with per-step live log panes in the run detail timeline.
- Added system-aware light/dark mode support with a top-right toggle in the web application header.
- Added a first-run onboarding wizard and workspace onboarding status APIs to guide setup through workspace naming, first project creation, and first provider connection.
- Added provider health probes with persisted status/error reporting, provider badges, and a dedicated health summary page.
- Added repo manifest introspection with build/test command suggestions and one-click "Use this" actions on the Projects page.
- Added per-language router defaults for planner/summarizer/audit/coder seed agents, with backfill migration coverage for existing installs.
