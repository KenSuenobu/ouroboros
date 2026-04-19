"""Shared tool-using LLM agent loop. Used by Anthropic, Ollama, and GH Models adapters."""

from __future__ import annotations

import json
from typing import Any

from ...db.models import Agent
from ..base import LLMMessage, ProviderRegistry, ResolvedModel, StepResult
from ..tools import TOOL_SCHEMAS, ToolContext, invoke_tool

MAX_TOOL_TURNS = 12


def _format_finish(result: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    return result.get("summary", ""), result.get("output", {}) or {}


async def llm_agent_loop(
    *,
    providers: ProviderRegistry,
    agent: Agent,
    model: ResolvedModel,
    ctx: Any,
    user_input: str,
) -> StepResult:
    provider = providers.get(model.provider_kind)
    tool_ctx = ToolContext(repo_path=ctx.sandbox_path, vfs=ctx.vfs, dry_run=ctx.dry_run)

    system = agent.system_prompt or ""
    if ctx.issue:
        system += "\n\nIssue context:\n" + json.dumps(ctx.issue, default=str)[:4000]

    messages: list[LLMMessage] = [
        LLMMessage(role="system", content=system),
        LLMMessage(role="user", content=user_input or "Begin."),
    ]

    artifacts: list[dict[str, Any]] = []
    summary = ""
    output: dict[str, Any] = {}
    tokens_in = 0
    tokens_out = 0
    warnings: list[str] = []

    for turn in range(MAX_TOOL_TURNS):
        result = await provider.complete(
            model, messages, tools=TOOL_SCHEMAS, max_tokens=4096, temperature=0.2
        )
        tokens_in += result.tokens_in
        tokens_out += result.tokens_out

        artifacts.append(
            {"kind": "response", "name": f"turn-{turn}-response", "inline_content": result.content}
        )

        if not result.tool_calls:
            summary = result.content[:2000]
            break

        messages.append(LLMMessage(role="assistant", content=result.content))

        finished = False
        for call in result.tool_calls:
            tool_name = call.get("name")
            tool_args = call.get("input") or call.get("arguments") or {}
            if isinstance(tool_args, str):
                try:
                    tool_args = json.loads(tool_args)
                except json.JSONDecodeError:
                    tool_args = {"raw": tool_args}
            if tool_name == "finish":
                summary, output = _format_finish(tool_args)
                finished = True
                continue
            tool_result = await invoke_tool(tool_name, tool_args, tool_ctx)
            artifacts.append(
                {
                    "kind": "tool_call",
                    "name": tool_name,
                    "inline_content": json.dumps(
                        {"args": tool_args, "result": tool_result}, default=str
                    ),
                }
            )
            if tool_result.get("blocked"):
                warnings.append(f"shell blocked in dry-run: {tool_args.get('command')!r}")
            messages.append(
                LLMMessage(
                    role="user",
                    content=f"Tool result for {tool_name}: {json.dumps(tool_result)[:6000]}",
                )
            )
        if finished:
            break
    else:
        warnings.append("max tool turns reached without finish()")

    if ctx.dry_run:
        for change in ctx.vfs.list_changes():
            artifacts.append(
                {
                    "kind": "file_diff",
                    "name": change["path"],
                    "inline_content": change["diff"],
                    "meta": {"kind": change["kind"]},
                }
            )

    return StepResult(
        summary=summary or "(no summary)",
        output=output,
        artifacts=artifacts,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=0.0,
        model_used=model.model_id,
        provider_id=model.provider_id,
        warnings=warnings,
    )
