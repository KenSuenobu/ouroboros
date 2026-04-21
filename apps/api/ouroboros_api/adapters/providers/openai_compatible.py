"""OpenAI-compatible provider: /v1/models and /v1/chat/completions."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx

from ..base import CompletionResult, LLMMessage, ResolvedModel


class OpenAICompatibleProvider:
    kind = "openai_compatible"

    def _base_url(self, model: ResolvedModel) -> str:
        return (model.base_url or "https://api.openai.com").rstrip("/")

    def _headers(self, model: ResolvedModel) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {model.api_key or ''}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def list_models(self, model: ResolvedModel) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(
            base_url=self._base_url(model), headers=self._headers(model), timeout=20.0
        ) as client:
            r = await client.get("/v1/models")
            r.raise_for_status()
            payload = r.json() or {}
            rows = payload.get("data", []) if isinstance(payload, dict) else []
        return [
            {
                "model_id": row.get("id", ""),
                "display_name": row.get("id", ""),
                "capabilities": ["chat"],
            }
            for row in rows
            if isinstance(row, dict) and row.get("id")
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
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools
        async with httpx.AsyncClient(
            base_url=self._base_url(model), headers=self._headers(model), timeout=120.0
        ) as client:
            r = await client.post("/v1/chat/completions", json=payload)
            r.raise_for_status()
            data = r.json()
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message", {}) or {}
        usage = data.get("usage", {}) or {}
        return CompletionResult(
            content=msg.get("content", "") or "",
            tool_calls=msg.get("tool_calls", []),
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
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
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        async with httpx.AsyncClient(
            base_url=self._base_url(model), headers=self._headers(model), timeout=None
        ) as client:
            async with client.stream("POST", "/v1/chat/completions", json=payload) as r:
                async for line in r.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    body = line[5:].strip()
                    if not body or body == "[DONE]":
                        continue
                    import json as _json

                    try:
                        evt = _json.loads(body)
                    except _json.JSONDecodeError:
                        continue
                    delta = ((evt.get("choices") or [{}])[0].get("delta") or {}).get("content")
                    if delta:
                        yield delta
