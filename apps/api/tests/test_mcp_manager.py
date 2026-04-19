"""MCP manager: stub session for unconfigured servers, registry caching."""

from __future__ import annotations

from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_registry_client_caches_results(monkeypatch: pytest.MonkeyPatch) -> None:
    from ouroboros_api.mcp.registry_client import RegistryClient

    client = RegistryClient(base_url="http://example.invalid")
    fake_payload = [{"id": "x", "name": "x"}]

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"servers": fake_payload}

    calls: list[str] = []

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *args) -> None:
            return None

        async def get(self, path: str, params: dict | None = None) -> FakeResponse:
            calls.append(path)
            return FakeResponse()

    monkeypatch.setattr("ouroboros_api.mcp.registry_client.httpx.AsyncClient", FakeAsyncClient)

    first = await client.list_servers("foo", limit=10)
    second = await client.list_servers("foo", limit=10)
    assert first == second
    assert len(calls) == 1, "second identical query should hit the cache"


@pytest.mark.asyncio
async def test_mcp_manager_returns_stub_for_invalid_install_spec() -> None:
    from ouroboros_api.mcp.manager import McpManager

    mgr = McpManager()
    fake_server = SimpleNamespace(
        id="srv-1",
        name="echo",
        transport="stdio",
        install_spec={},
        config={},
    )
    info = await mgr.open([fake_server])
    assert "echo" in info
    res = await mgr.call("echo", "any", {})
    assert res["ok"] is False
    await mgr.close()


@pytest.mark.asyncio
async def test_mcp_manager_call_unknown_server_is_safe() -> None:
    from ouroboros_api.mcp.manager import McpManager

    mgr = McpManager()
    res = await mgr.call("nope", "x", {})
    assert res["ok"] is False and "not started" in res["error"]
