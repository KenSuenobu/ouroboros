# Ouroboros

Local-first, multi-tenant-ready agent orchestration platform. Turns the
`/implement` workflow (and any workflow you can sketch in a flow designer) into
configurable, observable, dry-runnable agent pipelines wired to Ollama,
Anthropic, GitHub Models, opencode, and `gh copilot`.

- React/Next.js + Radix UI front end
- Python/FastAPI orchestrator
- SQLite locally (Postgres-ready schema)
- Per-agent execution adapters (CLI or direct LLM)
- React-Flow workflow + routing designer
- MCP registry browser + per-agent MCP bindings
- WebSocket live runs with mid-run interventions
- Dry-run by default, promote to real run on demand

## Quick start (local dev)

Prereqs: Python 3.12+, Node 20+, [`yarn`](https://yarnpkg.com/) 4+. Optional:
`ollama`, `opencode`, `gh`. **`uv` does not need to be pre-installed** — the
api workspace bootstraps a local `apps/api/.venv` and installs `uv` inside it
on first run.

```bash
cd apps/api
./scripts/with-venv.sh uv run ouroboros init  # Step 0: write local OUROBOROS_* defaults into .env/.env.example
cd ../..

make install       # installs root turbo + web deps via yarn, api deps via uv
make migrate       # creates the SQLite db and seeds defaults
make dev           # runs api on :8000 and web on :3000 in parallel via Turborepo
```

Open http://localhost:3000.

The monorepo uses [Yarn workspaces](https://yarnpkg.com/features/workspaces)
plus [Turborepo](https://turbo.build/), so both apps boot from a single
command. You can also drive turbo directly:

```bash
yarn dev            # = turbo run dev --parallel  (api + web together)
yarn build          # builds web (and `uv sync`s api)
yarn test           # pytest in api, vitest in web
yarn lint           # ruff in api, next lint in web
```

Need to run only one app? Use yarn workspaces or a turbo filter:

```bash
yarn workspace ouroboros-web dev
yarn turbo run dev --filter=@ouroboros/api
yarn turbo run dev --filter=ouroboros-web
```

Yarn 4 is enabled via `corepack`. If you don't have it yet:

```bash
corepack enable
corepack prepare yarn@4.5.3 --activate
```

## Layout

```
apps/api/    FastAPI orchestrator (Python)
apps/web/    Next.js 15 App Router UI
apps/cli/    Optional CLI: `ouroboros run <project> <issue>`
data/        Runtime state: SQLite, run sandboxes, artifacts, logs
docs/        Design docs and roadmaps
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full design and
[BUSINESS_MODEL.md](BUSINESS_MODEL.md) for the proposed commercial model.

## License

MIT for the open-core (orchestrator + adapters + UI). Hosted runtime, billing,
marketplace, SSO and RBAC are commercial - see `BUSINESS_MODEL.md`.
