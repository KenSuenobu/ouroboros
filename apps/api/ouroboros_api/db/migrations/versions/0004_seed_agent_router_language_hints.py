"""backfill router language hints for default agents

Revision ID: 0004_seed_agent_router_language_hints
Revises: 0003_provider_health_state
Create Date: 2026-04-19

"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from alembic import op

revision = "0004_seed_agent_router_language_hints"
down_revision = "0003_provider_health_state"
branch_labels = None
depends_on = None


PLANNING_LANGUAGE_MAP = {
    "python": {"prefer_kind": "anthropic", "model_hint": "sonnet"},
    "typescript": {"prefer_kind": "anthropic", "model_hint": "sonnet"},
}

CODER_LANGUAGE_MAP = {
    "python": {"prefer_kind": "ollama", "model_hint": "qwen2.5-coder"},
    "typescript": {"prefer_kind": "anthropic", "model_hint": "claude-sonnet"},
    "javascript": {"prefer_kind": "anthropic", "model_hint": "claude-sonnet"},
    "sql": {"prefer_kind": "ollama", "model_hint": "sqlcoder"},
    "rust": {"prefer_kind": "ollama", "model_hint": "qwen2.5-coder"},
}

LANGUAGE_MAP_BY_ROLE = {
    "issue.summarizer": PLANNING_LANGUAGE_MAP,
    "planner": PLANNING_LANGUAGE_MAP,
    "internal.audit": PLANNING_LANGUAGE_MAP,
    "coder": CODER_LANGUAGE_MAP,
}


def _needs_router_hints_update(policy: dict[str, Any]) -> bool:
    if (policy or {}).get("kind") != "router":
        return False
    hints = (policy.get("router_hints") or {}) if isinstance(policy, dict) else {}
    # Preserve existing language map customizations.
    if not isinstance(hints, dict):
        return True
    return not hints.get("language_map")


def upgrade() -> None:
    bind = op.get_bind()
    agents = sa.table(
        "agents",
        sa.column("id", sa.String()),
        sa.column("role", sa.String()),
        sa.column("model_policy", sa.JSON()),
    )

    rows = bind.execute(
        sa.select(agents.c.id, agents.c.role, agents.c.model_policy).where(
            agents.c.role.in_(tuple(LANGUAGE_MAP_BY_ROLE))
        )
    ).fetchall()

    for row in rows:
        role = row.role
        policy = row.model_policy or {}
        if role not in LANGUAGE_MAP_BY_ROLE or not _needs_router_hints_update(policy):
            continue

        hints = policy.get("router_hints") if isinstance(policy.get("router_hints"), dict) else {}
        hints = dict(hints)
        hints["language_map"] = LANGUAGE_MAP_BY_ROLE[role]

        patched_policy = dict(policy)
        patched_policy["kind"] = "router"
        patched_policy["router_hints"] = hints

        bind.execute(
            sa.update(agents).where(agents.c.id == row.id).values(model_policy=patched_policy)
        )


def downgrade() -> None:
    # Data backfill only; preserve user/customized policies.
    return None
