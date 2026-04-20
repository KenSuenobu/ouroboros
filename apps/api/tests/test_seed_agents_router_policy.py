from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ouroboros_api.db.models import Agent, Base
from ouroboros_api.seeds.bootstrap import bootstrap_if_empty


@pytest.mark.asyncio
async def test_bootstrap_seeds_language_maps_for_router_agents(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "seed-router-policy.sqlite"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        from ouroboros_api.db import session as session_module

        monkeypatch.setattr(session_module, "SessionLocal", session_factory)

        await bootstrap_if_empty()

        async with session_factory() as session:
            rows = (
                await session.execute(
                    select(Agent.role, Agent.model_policy).where(
                        Agent.role.in_(["issue.summarizer", "planner", "internal.audit", "coder"])
                    )
                )
            ).all()

        by_role = {role: policy for role, policy in rows}
        assert set(by_role) == {"issue.summarizer", "planner", "internal.audit", "coder"}

        for role in ("issue.summarizer", "planner", "internal.audit"):
            language_map = (by_role[role].get("router_hints") or {}).get("language_map") or {}
            assert language_map["python"]["prefer_kind"] == "anthropic"
            assert "sonnet" in language_map["python"]["model_hint"]
            assert language_map["typescript"]["prefer_kind"] == "anthropic"
            assert "sonnet" in language_map["typescript"]["model_hint"]

        coder_map = (by_role["coder"].get("router_hints") or {}).get("language_map") or {}
        assert coder_map["python"]["prefer_kind"] == "ollama"
        assert "qwen" in coder_map["python"]["model_hint"]
        assert coder_map["typescript"]["prefer_kind"] == "anthropic"
        assert "sonnet" in coder_map["typescript"]["model_hint"]
        assert coder_map["sql"]["prefer_kind"] == "ollama"
        assert "sqlcoder" in coder_map["sql"]["model_hint"]
    finally:
        await engine.dispose()
