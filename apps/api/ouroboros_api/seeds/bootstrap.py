"""First-run bootstrap: default workspace, default agents, default flow,
optional admin user from env vars.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from sqlalchemy import func, select

from ..config import settings
from ..db.models import Agent, Flow, User, Workspace, WorkspaceMembership
from ..services import auth as auth_svc
from .agents import DEFAULT_AGENTS

SEEDS_DIR = Path(__file__).resolve().parent
log = logging.getLogger("ouroboros.bootstrap")


async def _seed_default_workspace() -> None:
    from ..db.session import SessionLocal

    async with SessionLocal() as session:
        if (await session.execute(select(Workspace))).scalars().first():
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


async def _seed_bootstrap_admin() -> None:
    """Create an admin user from OUROBOROS_AUTH_BOOTSTRAP_ADMIN_* if no users exist."""
    from ..db.session import SessionLocal

    email = (settings.auth_bootstrap_admin_email or "").strip().lower()
    password = settings.auth_bootstrap_admin_password
    if not email or not password:
        return

    async with SessionLocal() as session:
        existing = await session.scalar(select(func.count(User.id)))
        if existing and existing > 0:
            return
        ws = (
            await session.execute(
                select(Workspace).where(Workspace.slug == settings.default_workspace_slug)
            )
        ).scalar_one_or_none()
        if not ws:
            log.warning("bootstrap admin requested but default workspace is missing")
            return
        user = User(
            email=email,
            display_name=settings.auth_bootstrap_admin_name or email.split("@")[0],
            password_hash=auth_svc.hash_password(password),
            is_active=True,
        )
        session.add(user)
        await session.flush()
        session.add(
            WorkspaceMembership(user_id=user.id, workspace_id=ws.id, role="admin")
        )
        await session.commit()
        log.info("seeded bootstrap admin user %s", email)


async def bootstrap_if_empty() -> None:
    await _seed_default_workspace()
    await _seed_bootstrap_admin()


def main() -> None:
    asyncio.run(bootstrap_if_empty())


if __name__ == "__main__":
    main()
