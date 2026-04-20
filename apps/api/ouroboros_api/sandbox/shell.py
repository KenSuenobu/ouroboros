"""Constrained subprocess runner with classification for dry-run safety."""

from __future__ import annotations

import asyncio
import inspect
import shlex
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
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

LineSink = Callable[[str, str], Awaitable[None] | None]
_SHELL_LINE_SINK: ContextVar[LineSink | None] = ContextVar("shell_line_sink", default=None)


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


@contextmanager
def shell_line_subscriber(sink: LineSink) -> Iterator[None]:
    """Temporarily subscribe to stdout/stderr lines emitted by run_shell."""
    token = _SHELL_LINE_SINK.set(sink)
    try:
        yield
    finally:
        _SHELL_LINE_SINK.reset(token)


async def iter_process_lines(proc: asyncio.subprocess.Process) -> AsyncIterator[tuple[str, str]]:
    """Yield process output as (stream, line) tuples in near real-time."""
    if proc.stdout is None or proc.stderr is None:
        return

    queue: asyncio.Queue[tuple[str, str | None]] = asyncio.Queue()

    async def _pump(reader: asyncio.StreamReader, stream: str) -> None:
        while True:
            line = await reader.readline()
            if not line:
                break
            await queue.put((stream, line.decode("utf-8", errors="replace")))
        await queue.put((stream, None))

    stdout_task = asyncio.create_task(_pump(proc.stdout, "stdout"))
    stderr_task = asyncio.create_task(_pump(proc.stderr, "stderr"))
    done = 0
    while done < 2:
        stream, line = await queue.get()
        if line is None:
            done += 1
            continue
        yield (stream, line)
    await stdout_task
    await stderr_task


async def _emit_line(sink: LineSink | None, stream: str, line: str) -> None:
    if sink is None:
        return
    maybe_awaitable = sink(stream, line)
    if inspect.isawaitable(maybe_awaitable):
        await maybe_awaitable


async def run_shell(
    cmd: str,
    *,
    cwd: Path,
    dry_run: bool = False,
    env: dict[str, str] | None = None,
    timeout: float = 600.0,
    allow_side_effect: bool = False,
    on_line: LineSink | None = None,
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
    sink = on_line or _SHELL_LINE_SINK.get()
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []

    async def _collect_lines() -> None:
        async for stream, line in iter_process_lines(proc):
            if stream == "stdout":
                stdout_parts.append(line)
            else:
                stderr_parts.append(line)
            await _emit_line(sink, stream, line)
        await proc.wait()

    try:
        await asyncio.wait_for(_collect_lines(), timeout=timeout)
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
    except asyncio.CancelledError:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
        raise
    return ShellResult(
        cmd=cmd,
        classification=classification,
        cwd=str(cwd),
        exit_code=proc.returncode or 0,
        stdout="".join(stdout_parts),
        stderr="".join(stderr_parts),
    )
