"""Router agent: classifies the task and recommends a provider+model per agent.

Two paths:
- Heuristic baseline (zero LLM call): file extensions in the issue body / labels -> a
  language hint -> map to a provider via Agent.model_policy.router_hints.language_map.
- (Future) LLM-backed router: feed inventory + issue summary to the Router agent.
  This module exposes the heuristic; the LLM router runs as a normal agent step.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from ..db.models import Agent, Provider, ProviderModel

EXT_TO_LANG = {
    ".py": "python",
    ".pyi": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".sql": "sql",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".rb": "ruby",
}

LABEL_TO_LANG = {
    "python": "python",
    "py": "python",
    "typescript": "typescript",
    "ts": "typescript",
    "javascript": "javascript",
    "js": "javascript",
    "sql": "sql",
    "database": "sql",
    "db": "sql",
    "rust": "rust",
}


def detect_language(issue: dict[str, Any] | None) -> str | None:
    if not issue:
        return None
    body = (issue.get("body") or "") + " " + (issue.get("title") or "")
    for ext, lang in EXT_TO_LANG.items():
        if re.search(rf"\b\w+{re.escape(ext)}\b", body):
            return lang
    for lbl in (issue.get("labels") or []):
        lbl_lower = (lbl or "").lower()
        if lbl_lower in LABEL_TO_LANG:
            return LABEL_TO_LANG[lbl_lower]
    return None


def pick_model(
    agent: Agent,
    providers: Iterable[Provider],
    models: dict[str, list[ProviderModel]],
    issue: dict[str, Any] | None,
    overrides: dict[str, Any] | None = None,
) -> tuple[Provider, ProviderModel] | None:
    """Apply Agent.model_policy + heuristic to choose (Provider, ProviderModel).

    `overrides` per-run takes precedence, then policy, then any enabled provider's first model.
    """
    overrides = overrides or {}
    role_override = overrides.get(agent.role) or {}
    policy = agent.model_policy or {}

    target_provider_id = role_override.get("provider_id") or policy.get("fixed_provider_id")
    target_model_id = role_override.get("model_id") or policy.get("fixed_model_id")

    enabled = [p for p in providers if p.enabled]

    if target_provider_id:
        provider = next((p for p in enabled if p.id == target_provider_id), None)
        if provider:
            options = models.get(provider.id, [])
            chosen = next((m for m in options if m.model_id == target_model_id), options[0] if options else None)
            if chosen:
                return provider, chosen

    if (policy.get("kind") or "router") == "router":
        lang = detect_language(issue)
        hints = (policy.get("router_hints") or {}).get("language_map", {})
        if lang and lang in hints:
            hint = hints[lang]
            kind = hint.get("prefer_kind")
            model_hint = hint.get("model_hint", "").lower()
            for provider in enabled:
                if kind and provider.kind != kind:
                    continue
                options = models.get(provider.id, [])
                if not options:
                    continue
                if model_hint:
                    matched = next((m for m in options if model_hint in m.model_id.lower()), None)
                    if matched:
                        return provider, matched
                return provider, options[0]

    for provider in enabled:
        options = models.get(provider.id, [])
        if options:
            return provider, options[0]
    return None
