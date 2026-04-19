"""Direct-Anthropic agent execution adapter."""

from __future__ import annotations

from typing import Any

from ..base import ProviderRegistry, ResolvedModel, StepResult
from ._llm_loop import llm_agent_loop


class AnthropicAgentAdapter:
    name = "anthropic_api"

    def __init__(self, providers: ProviderRegistry) -> None:
        self.providers = providers

    async def run(self, ctx: Any, agent: Any, model: ResolvedModel) -> StepResult:
        user_input = ctx.scratchpad.get("agent_input", "")
        return await llm_agent_loop(
            providers=self.providers, agent=agent, model=model, ctx=ctx, user_input=user_input
        )
