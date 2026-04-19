"""gh copilot CLI execution adapter (suggest / explain modes)."""

from __future__ import annotations

import asyncio
import shutil
from typing import Any

from ..base import ResolvedModel, StepResult


class GhCopilotCliAdapter:
    name = "gh_copilot_cli"

    async def run(self, ctx: Any, agent: Any, model: ResolvedModel) -> StepResult:
        if shutil.which("gh") is None:
            return StepResult(
                summary="gh binary not found",
                failed=True,
                error="gh CLI not installed",
                model_used=model.model_id,
                provider_id=model.provider_id,
            )
        prompt = ctx.scratchpad.get("agent_input", "") or agent.system_prompt or ""
        mode = (agent.config or {}).get("mode", "suggest")
        proc = await asyncio.create_subprocess_exec(
            "gh", "copilot", mode, prompt,
            cwd=str(ctx.sandbox_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        stdout = out.decode("utf-8", errors="replace")
        stderr = err.decode("utf-8", errors="replace")
        if proc.returncode != 0:
            return StepResult(
                summary="gh copilot failed",
                artifacts=[
                    {"kind": "shell_log", "name": "gh.stdout", "inline_content": stdout},
                    {"kind": "shell_log", "name": "gh.stderr", "inline_content": stderr},
                ],
                failed=True,
                error=stderr,
                model_used=model.model_id,
                provider_id=model.provider_id,
            )
        return StepResult(
            summary=stdout.strip().splitlines()[0][:200] if stdout else "ok",
            output={"text": stdout},
            artifacts=[{"kind": "response", "name": "gh.copilot", "inline_content": stdout}],
            model_used=model.model_id,
            provider_id=model.provider_id,
        )
