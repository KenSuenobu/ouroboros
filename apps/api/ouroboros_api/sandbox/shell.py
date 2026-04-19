"""Constrained subprocess runner with classification for dry-run safety."""

from __future__ import annotations

import asyncio
import shlex
from dataclasses import dataclass
from pathlib import Path

SIDE_EFFECT_PATTERNS = (
    "git push",
    "git tag",
    "git remote add",
    "gh pr create",
    "gh pr edit",
    "gh issue comment",
    "gh issue close",
    "gh release create",
    "npm publish",
    "yarn publish",
    "pnpm publish",
    "uv publish",
    "twine upload",
    "docker push",
    "rm -rf /",
    "sudo ",
)

BUILD_PATTERNS = ("npm run build", "yarn build", "pnpm build", "uv build", "make build", "cargo build")
TEST_PATTERNS = ("npm test", "yarn test", "pnpm test", "uv run pytest", "pytest", "make test", "cargo test")


def classify_command(cmd: str) -> str:
    lower = cmd.strip().lower()
    if any(p in lower for p in SIDE_EFFECT_PATTERNS):
        return "side_effect"
    if any(p in lower for p in BUILD_PATTERNS):
        return "build"
    if any(p in lower for p in TEST_PATTERNS):
        return "test"
    if lower.startswith(("ls", "cat", "head", "tail", "grep", "rg", "find", "git status", "git log", "git diff", "git show")):
        return "read"
    return "other"


@dataclass
class ShellResult:
    cmd: str
    classification: str
    cwd: str
    exit_code: int
    stdout: str
    stderr: str
    blocked: bool = False
    reason: str | None = None

    @property
    def succeeded(self) -> bool:
        return not self.blocked and self.exit_code == 0


async def run_shell(
    cmd: str,
    *,
    cwd: Path,
    dry_run: bool = False,
    env: dict[str, str] | None = None,
    timeout: float = 600.0,
    allow_side_effect: bool = False,
) -> ShellResult:
    classification = classify_command(cmd)
    if dry_run and classification == "side_effect" and not allow_side_effect:
        return ShellResult(
            cmd=cmd,
            classification=classification,
            cwd=str(cwd),
            exit_code=0,
            stdout="",
            stderr="",
            blocked=True,
            reason="side-effecting command suppressed in dry-run",
        )

    args = shlex.split(cmd)
    proc = await asyncio.create_subprocess_exec(
        *args,
        cwd=str(cwd),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        return ShellResult(
            cmd=cmd,
            classification=classification,
            cwd=str(cwd),
            exit_code=-1,
            stdout="",
            stderr="timeout",
            blocked=True,
            reason="timeout",
        )
    return ShellResult(
        cmd=cmd,
        classification=classification,
        cwd=str(cwd),
        exit_code=proc.returncode or 0,
        stdout=out.decode("utf-8", errors="replace"),
        stderr=err.decode("utf-8", errors="replace"),
    )
