"""Anthropic provider: Messages API. Uses the official SDK when present, HTTP otherwise."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx

from ..base import CompletionResult, LLMMessage, ResolvedModel

DEFAULT_MODEL_CATALOG = [
    {"model_id": "claude-3-5-sonnet-latest", "display_name": "Claude 3.5 Sonnet", "context_window": 200000,
     "input_cost_per_mtok": 3.0, "output_cost_per_mtok": 15.0},
    {"model_id": "claude-3-5-haiku-latest", "display_name": "Claude 3.5 Haiku", "context_window": 200000,
     "input_cost_per_mtok": 0.8, "output_cost_per_mtok": 4.0},
    {"model_id": "claude-3-opus-latest", "display_name": "Claude 3 Opus", "context_window": 200000,
     "input_cost_per_mtok": 15.0, "output_cost_per_mtok": 75.0},
]


class AnthropicProvider:
    kind = "anthropic"

    def _base_url(self, model: ResolvedModel) -> str:
        return (model.base_url or "https://api.anthropic.com").rstrip("/")

    def _headers(self, model: ResolvedModel) -> dict[str, str]:
        return {
            "x-api-key": model.api_key or "",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    async def list_models(self, model: ResolvedModel) -> list[dict[str, Any]]:
        # Anthropic doesn't expose a public listing endpoint; return curated catalog.
        return [{**m, "capabilities": ["chat", "tools", "reasoning"]} for m in DEFAULT_MODEL_CATALOG]

    @staticmethod
    def _split_system(messages: list[LLMMessage]) -> tuple[str | None, list[dict[str, Any]]]:
        system_parts = [m.content for m in messages if m.role == "system"]
        rest = [
            {"role": m.role if m.role in {"user", "assistant"} else "user", "content": m.content}
            for m in messages
            if m.role != "system"
        ]
        return ("\n\n".join(system_parts) or None), rest

    async def complete(
        self,
        model: ResolvedModel,
        messages: list[LLMMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> CompletionResult:
        system, rest = self._split_system(messages)
        payload: dict[str, Any] = {
            "model": model.model_id,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": rest,
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(
            base_url=self._base_url(model), headers=self._headers(model), timeout=120.0
        ) as client:
            r = await client.post("/v1/messages", json=payload)
            r.raise_for_status()
            data = r.json()

        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        for block in data.get("content", []) or []:
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                tool_calls.append({"id": block.get("id"), "name": block.get("name"), "input": block.get("input")})

        usage = data.get("usage", {})
        return CompletionResult(
            content="".join(text_parts),
            tool_calls=tool_calls,
            tokens_in=usage.get("input_tokens", 0),
            tokens_out=usage.get("output_tokens", 0),
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
        # Minimal SSE handler.
        system, rest = self._split_system(messages)
        payload: dict[str, Any] = {
            "model": model.model_id,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": rest,
            "stream": True,
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = tools
        async with httpx.AsyncClient(
            base_url=self._base_url(model), headers=self._headers(model), timeout=None
        ) as client:
            async with client.stream("POST", "/v1/messages", json=payload) as r:
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
                    if evt.get("type") == "content_block_delta":
                        delta = (evt.get("delta") or {}).get("text")
                        if delta:
                            yield delta
