"""Ollama provider: HTTP API at /api/tags and /api/chat."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx

from ..base import CompletionResult, LLMMessage, ResolvedModel


class OllamaProvider:
    kind = "ollama"

    def _base_url(self, model: ResolvedModel) -> str:
        return (model.base_url or "http://localhost:11434").rstrip("/")

    async def list_models(self, model: ResolvedModel) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(base_url=self._base_url(model), timeout=15.0) as client:
            r = await client.get("/api/tags")
            r.raise_for_status()
            return [
                {
                    "model_id": m["name"],
                    "display_name": m["name"],
                    "context_window": (m.get("details") or {}).get("parameter_size"),
                    "capabilities": ["chat"],
                }
                for m in r.json().get("models", [])
            ]

    async def complete(
        self,
        model: ResolvedModel,
        messages: list[LLMMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> CompletionResult:
        payload: dict[str, Any] = {
            "model": model.model_id,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if tools:
            payload["tools"] = tools
        async with httpx.AsyncClient(base_url=self._base_url(model), timeout=120.0) as client:
            r = await client.post("/api/chat", json=payload)
            r.raise_for_status()
            data = r.json()
        msg = data.get("message", {}) or {}
        return CompletionResult(
            content=msg.get("content", ""),
            tool_calls=msg.get("tool_calls", []),
            tokens_in=data.get("prompt_eval_count", 0),
            tokens_out=data.get("eval_count", 0),
            raw=data,
        )

    async def stream(
        self,
        model: ResolvedModel,
        messages: list[LLMMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> AsyncIterator[str]:
        payload: dict[str, Any] = {
            "model": model.model_id,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        async with httpx.AsyncClient(base_url=self._base_url(model), timeout=None) as client:
            async with client.stream("POST", "/api/chat", json=payload) as r:
                async for line in r.aiter_lines():
                    if not line.strip():
                        continue
                    import json as _json

                    try:
                        chunk = _json.loads(line)
                    except _json.JSONDecodeError:
                        continue
                    delta = (chunk.get("message") or {}).get("content")
                    if delta:
                        yield delta
