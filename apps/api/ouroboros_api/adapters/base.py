"""Adapter and provider abstractions."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class LLMMessage:
    role: str
    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None


@dataclass
class ResolvedModel:
    """The concrete model selected for one step."""

    provider_id: str
    provider_kind: str
    model_id: str
    base_url: str | None = None
    api_key: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompletionResult:
    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


class LLMProvider(Protocol):
    """Provider-level: list models + chat-complete. Used by the router agent and chat tester."""

    kind: str

    async def list_models(self, model: ResolvedModel) -> list[dict[str, Any]]: ...

    async def complete(
        self,
        model: ResolvedModel,
        messages: list[LLMMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> CompletionResult: ...

    async def stream(
        self,
        model: ResolvedModel,
        messages: list[LLMMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> AsyncIterator[str]: ...


@dataclass
class StepResult:
    summary: str
    output: dict[str, Any] = field(default_factory=dict)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    model_used: str | None = None
    provider_id: str | None = None
    warnings: list[str] = field(default_factory=list)
    failed: bool = False
    error: str | None = None


class RunContext(Protocol):
    """Light protocol; the real RunContext lives in orchestrator.context."""

    workspace_id: str
    project_id: str
    run_id: str
    sandbox_path: Any
    dry_run: bool
    scratchpad: dict[str, Any]
    issue: dict[str, Any] | None

    async def emit(self, event: str, payload: dict[str, Any]) -> None: ...


class AgentExecutionAdapter(Protocol):
    """Per-agent execution: orchestrator hands the agent + ctx + selected model and gets a StepResult."""

    name: str

    async def run(self, ctx: RunContext, agent: Any, model: ResolvedModel) -> StepResult: ...


class ProviderRegistry:
    """Mapping of provider kind -> LLMProvider implementation."""

    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}

    def register(self, provider: LLMProvider) -> None:
        self._providers[provider.kind] = provider

    def get(self, kind: str) -> LLMProvider:
        if kind not in self._providers:
            raise KeyError(f"No LLM provider for kind={kind!r}")
        return self._providers[kind]

    def kinds(self) -> list[str]:
        return list(self._providers)


class AdapterRegistry:
    """Mapping of execution_adapter name -> AgentExecutionAdapter implementation."""

    def __init__(self) -> None:
        self._adapters: dict[str, AgentExecutionAdapter] = {}

    def register(self, adapter: AgentExecutionAdapter) -> None:
        self._adapters[adapter.name] = adapter

    def get(self, name: str) -> AgentExecutionAdapter:
        if name not in self._adapters:
            raise KeyError(f"No execution adapter for name={name!r}")
        return self._adapters[name]

    def names(self) -> list[str]:
        return list(self._adapters)
