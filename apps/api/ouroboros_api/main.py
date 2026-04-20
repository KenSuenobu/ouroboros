"""FastAPI app entrypoint. Wires routers, CORS, and the WebSocket hub."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import (
    agents,
    flows,
    issues,
    mcp,
    projects,
    providers,
    roadmap,
    runs,
    workspaces,
    ws,
)
from .config import settings
from .db.session import SessionLocal, init_db
from .orchestrator.engine import interrupt_in_flight_runs

logging.basicConfig(level=settings.log_level)
log = logging.getLogger("ouroboros")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_dirs()
    await init_db()
    async with SessionLocal() as session:
        interrupted = await interrupt_in_flight_runs(session)
    if interrupted:
        log.info("marked %s in-flight runs as interrupted at startup", interrupted)
    log.info("ouroboros api ready (data_dir=%s)", settings.data_dir)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Ouroboros",
        version="0.1.0",
        description="Agent orchestration platform: configurable, dry-runnable, observable.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(workspaces.router)
    app.include_router(projects.router)
    app.include_router(issues.router)
    app.include_router(roadmap.router)
    app.include_router(providers.router)
    app.include_router(agents.router)
    app.include_router(flows.router)
    app.include_router(mcp.router)
    app.include_router(runs.router)
    app.include_router(ws.router)

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()


def run() -> None:
    """Console-script entrypoint."""
    import uvicorn

    uvicorn.run(
        "ouroboros_api.main:app",
        host=settings.bind_host,
        port=settings.bind_port,
        reload=False,
    )


if __name__ == "__main__":
    run()
