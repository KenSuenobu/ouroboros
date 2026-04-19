"""opencode CLI execution adapter.

Spawns `opencode run --quiet --json --model <model> <prompt>` in the sandbox repo
and parses the JSON envelope. Falls back to plain text if --json isn't supported.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from typing import Any

from ..base import ResolvedModel, StepResult


class OpencodeCliAdapter:
    name = "opencode_cli"

    async def run(self, ctx: Any, agent: Any, model: ResolvedModel) -> StepResult:
        if shutil.which("opencode") is None:
            return StepResult(
                summary="opencode binary not found",
                failed=True,
                error="opencode CLI not installed; install from https://opencode.ai or pick another adapter",
                model_used=model.model_id,
                provider_id=model.provider_id,
            )
        prompt = (agent.system_prompt or "") + "\n\n" + (ctx.scratchpad.get("agent_input", "") or "")
        args = ["opencode", "run", "--quiet"]
        if model.model_id:
            args += ["--model", model.model_id]
        if ctx.dry_run:
            args += ["--read-only"]
        args.append(prompt)

        proc = await asyncio.create_subprocess_exec(
            *args,
            cwd=str(ctx.sandbox_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        stdout = out.decode("utf-8", errors="replace")
        stderr = err.decode("utf-8", errors="replace")

        artifacts: list[dict[str, Any]] = [
            {"kind": "shell_log", "name": "opencode.stdout", "inline_content": stdout},
            {"kind": "shell_log", "name": "opencode.stderr", "inline_content": stderr},
        ]
        if proc.returncode != 0:
            return StepResult(
                summary=stderr.strip().splitlines()[-1] if stderr else "opencode failed",
                artifacts=artifacts,
                failed=True,
                error=stderr or stdout,
                model_used=model.model_id,
                provider_id=model.provider_id,
            )
        summary = stdout.strip().splitlines()[-1] if stdout.strip() else "opencode completed"
        try:
            output = json.loads(stdout)
        except json.JSONDecodeError:
            output = {"text": stdout}
        return StepResult(
            summary=summary[:2000],
            output=output if isinstance(output, dict) else {"text": str(output)},
            artifacts=artifacts,
            model_used=model.model_id,
            provider_id=model.provider_id,
        )
