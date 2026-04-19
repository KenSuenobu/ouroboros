"""First-run bootstrap: default workspace, default agents, default flow."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from ..config import settings
from ..db.models import Agent, Flow, Workspace
from .agents import DEFAULT_AGENTS

SEEDS_DIR = Path(__file__).resolve().parent


async def bootstrap_if_empty() -> None:
    from ..db.session import SessionLocal

    async with SessionLocal() as session:
        result = await session.execute(select(Workspace))
        if result.scalars().first():
            return

        ws = Workspace(slug=settings.default_workspace_slug, name="Default Workspace")
        session.add(ws)
        await session.flush()

        for spec in DEFAULT_AGENTS:
            session.add(
                Agent(
                    workspace_id=ws.id,
                    name=spec["name"],
                    role=spec["role"],
                    description=spec.get("description"),
                    system_prompt=spec.get("system_prompt", ""),
                    execution_adapter=spec["execution_adapter"],
                    model_policy=spec.get("model_policy", {"kind": "router"}),
                    config=spec.get("config", {}),
                    dry_run_default=spec.get("dry_run_default", False),
                    is_builtin=True,
                )
            )

        flow_spec = json.loads((SEEDS_DIR / "implement_flow.json").read_text("utf-8"))
        session.add(
            Flow(
                workspace_id=ws.id,
                name=flow_spec["name"],
                description=flow_spec.get("description"),
                graph={"nodes": flow_spec["nodes"], "edges": flow_spec["edges"]},
                is_default=True,
            )
        )
        await session.commit()


def main() -> None:
    asyncio.run(bootstrap_if_empty())


if __name__ == "__main__":
    main()
