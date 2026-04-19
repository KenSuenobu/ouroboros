"""Shared tool layer for LLM-backed agent adapters.

Adapters expose these tools to the LLM. In dry-run, writes go through VirtualFs
and side-effecting shell commands are blocked.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..sandbox.shell import run_shell
from ..sandbox.virtual_fs import VirtualFs


@dataclass
class ToolContext:
    repo_path: Path
    vfs: VirtualFs
    dry_run: bool


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "read_file",
        "description": "Read a UTF-8 file from the project. Path is relative to the repo root.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write a UTF-8 file. Creates parent dirs. In dry-run, write is virtual.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_files",
        "description": "List files matching a glob pattern, relative to repo root.",
        "input_schema": {
            "type": "object",
            "properties": {"pattern": {"type": "string", "default": "**/*"}},
        },
    },
    {
        "name": "run_shell",
        "description": "Run a shell command at the repo root. Side-effecting commands are blocked in dry-run.",
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}, "timeout_seconds": {"type": "integer", "default": 600}},
            "required": ["command"],
        },
    },
    {
        "name": "finish",
        "description": "Signal that the agent is done. Provide a short summary and any structured output.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "output": {"type": "object"},
            },
            "required": ["summary"],
        },
    },
]


async def invoke_tool(name: str, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    if name == "read_file":
        path = args.get("path", "")
        try:
            return {"ok": True, "content": ctx.vfs.read_file(path)}
        except FileNotFoundError:
            return {"ok": False, "error": f"file not found: {path}"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    if name == "write_file":
        path = args.get("path", "")
        content = args.get("content", "")
        try:
            if ctx.dry_run:
                ctx.vfs.write_file(path, content)
            else:
                target = (ctx.repo_path / path).resolve()
                if not str(target).startswith(str(ctx.repo_path)):
                    return {"ok": False, "error": "path escapes sandbox"}
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            return {"ok": True, "path": path, "bytes": len(content.encode("utf-8"))}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    if name == "list_files":
        pattern = args.get("pattern", "**/*")
        try:
            matches = [
                str(p.relative_to(ctx.repo_path))
                for p in ctx.repo_path.glob(pattern)
                if p.is_file()
            ]
            return {"ok": True, "files": matches[:500]}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    if name == "run_shell":
        cmd = args.get("command", "")
        timeout = float(args.get("timeout_seconds", 600))
        result = await run_shell(cmd, cwd=ctx.repo_path, dry_run=ctx.dry_run, timeout=timeout)
        return {
            "ok": result.succeeded,
            "exit_code": result.exit_code,
            "stdout": result.stdout[-8000:],
            "stderr": result.stderr[-4000:],
            "blocked": result.blocked,
            "reason": result.reason,
            "classification": result.classification,
        }

    if name == "finish":
        return {"ok": True, "summary": args.get("summary", ""), "output": args.get("output", {})}

    return {"ok": False, "error": f"unknown tool: {name}"}
