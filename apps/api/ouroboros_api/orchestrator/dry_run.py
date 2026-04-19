"""Dry-run helpers. Most of the heavy lifting lives in sandbox.virtual_fs and sandbox.shell."""

from __future__ import annotations

from typing import Any


def is_dry_run(run: Any, agent: Any | None = None, node: dict[str, Any] | None = None) -> bool:
    if getattr(run, "dry_run", False):
        return True
    if agent is not None and getattr(agent, "dry_run_default", False):
        return True
    if node and (node.get("config") or {}).get("dry_run", False):
        return True
    return False


def step_is_side_effecting(node: dict[str, Any]) -> bool:
    return bool((node.get("config") or {}).get("side_effecting"))
