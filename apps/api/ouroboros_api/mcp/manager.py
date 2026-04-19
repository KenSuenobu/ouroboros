"""Per-step MCP server manager.

Spawns the configured stdio MCP servers using the official `mcp` Python SDK,
exposes their tools, and tears them down at end of step.
"""

from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any

from ..db.models import McpServer


@dataclass
class McpSessionInfo:
    name: str
    tools: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


class _StubSession:
    """Fallback used when the `mcp` SDK is missing or the server failed to start."""

    def __init__(self, name: str, error: str) -> None:
        self.name = name
        self.error = error

    async def list_tools(self) -> list[dict[str, Any]]:
        return []

    async def call_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        return {"ok": False, "error": self.error or "stub session"}

    async def close(self) -> None:
        return None


class McpManager:
    def __init__(self) -> None:
        self._stack: AsyncExitStack | None = None
        self._sessions: dict[str, Any] = {}

    async def open(self, servers: list[McpServer]) -> dict[str, McpSessionInfo]:
        self._stack = AsyncExitStack()
        info: dict[str, McpSessionInfo] = {}
        for srv in servers:
            try:
                session = await self._spawn(srv)
                self._sessions[srv.name] = session
                tools = await session.list_tools()
                info[srv.name] = McpSessionInfo(name=srv.name, tools=tools)
            except Exception as exc:
                self._sessions[srv.name] = _StubSession(srv.name, str(exc))
                info[srv.name] = McpSessionInfo(name=srv.name, error=str(exc))
        return info

    async def close(self) -> None:
        for session in self._sessions.values():
            try:
                await session.close()
            except Exception:
                pass
        self._sessions.clear()
        if self._stack:
            await self._stack.aclose()
            self._stack = None

    async def call(self, server: str, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        session = self._sessions.get(server)
        if not session:
            return {"ok": False, "error": f"server {server!r} not started"}
        try:
            return await session.call_tool(tool, args)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def _spawn(self, srv: McpServer) -> Any:
        spec = srv.install_spec or {}
        try:
            from mcp import ClientSession  # type: ignore[import-not-found]
            from mcp.client.stdio import StdioServerParameters, stdio_client  # type: ignore[import-not-found]
        except Exception as exc:
            return _StubSession(srv.name, f"mcp SDK not available: {exc}")

        if srv.transport != "stdio":
            return _StubSession(srv.name, f"transport {srv.transport!r} not implemented")

        command = spec.get("command")
        args = spec.get("args", [])
        env = spec.get("env")
        if not command:
            return _StubSession(srv.name, "install_spec.command is required for stdio servers")

        params = StdioServerParameters(command=command, args=list(args), env=env)
        try:
            read, write = await self._stack.enter_async_context(stdio_client(params))  # type: ignore[union-attr]
            session = await self._stack.enter_async_context(ClientSession(read, write))  # type: ignore[union-attr]
            await asyncio.wait_for(session.initialize(), timeout=20.0)
            return _SdkSessionWrapper(session)
        except Exception as exc:
            return _StubSession(srv.name, f"failed to start MCP server: {exc}")


class _SdkSessionWrapper:
    def __init__(self, session: Any) -> None:
        self.session = session

    async def list_tools(self) -> list[dict[str, Any]]:
        try:
            res = await self.session.list_tools()
            return [
                {"name": t.name, "description": getattr(t, "description", ""), "input_schema": getattr(t, "inputSchema", {})}
                for t in getattr(res, "tools", [])
            ]
        except Exception:
            return []

    async def call_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        result = await self.session.call_tool(name, args)
        try:
            return {"ok": True, "content": [getattr(c, "text", str(c)) for c in getattr(result, "content", [])]}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def close(self) -> None:
        return None
