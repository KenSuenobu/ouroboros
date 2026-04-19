# ouroboros-api

FastAPI orchestrator for Ouroboros.

## Layout

```
ouroboros_api/
  main.py                 ASGI entrypoint
  config.py               Settings (env + .env)
  db/                     SQLAlchemy 2.x async + Alembic migrations
  api/                    REST routers
  orchestrator/           Run engine, router agent, dry-run, interventions
  adapters/               Per-agent execution adapters (CLI / direct LLM)
  sandbox/                Per-run git clones + constrained shell
  mcp/                    Registry client + per-step server manager
  scm/                    GitHub / GitLab issue fetchers
  services/               Plan visualization and other services
  seeds/                  Default flows + bootstrap script
tests/
```

## Dev

```bash
uv sync
uv run alembic upgrade head
uv run python -m ouroboros_api.seeds.bootstrap
uv run uvicorn ouroboros_api.main:app --reload --port 8000
```

OpenAPI lives at http://localhost:8000/docs.
