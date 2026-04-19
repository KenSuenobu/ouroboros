"""Client for the public MCP registry (registry.modelcontextprotocol.io)."""

from __future__ import annotations

import time
from typing import Any

import httpx

from ..config import settings


class RegistryClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.mcp_registry_url).rstrip("/")
        self._cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}

    async def list_servers(self, q: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        cache_key = f"{q or ''}:{limit}"
        now = time.time()
        cached = self._cache.get(cache_key)
        if cached and now - cached[0] < settings.mcp_registry_cache_ttl_seconds:
            return cached[1]

        params: dict[str, Any] = {"limit": limit}
        if q:
            params["q"] = q

        async with httpx.AsyncClient(base_url=self.base_url, timeout=20.0) as client:
            try:
                r = await client.get("/v0/servers", params=params)
                r.raise_for_status()
                data = r.json()
            except Exception:
                return []
        servers = data.get("servers") if isinstance(data, dict) else data
        if not isinstance(servers, list):
            servers = []

        result = [self._normalize(s) for s in servers]
        self._cache[cache_key] = (now, result)
        return result

    async def get_server(self, server_id: str) -> dict[str, Any] | None:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=20.0) as client:
            try:
                r = await client.get(f"/v0/servers/{server_id}")
                r.raise_for_status()
                return self._normalize(r.json())
            except Exception:
                return None

    @staticmethod
    def _normalize(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": item.get("id") or item.get("name") or "",
            "name": item.get("name") or item.get("displayName") or item.get("id") or "",
            "description": item.get("description") or item.get("summary"),
            "repository": (item.get("repository") or {}).get("url")
            if isinstance(item.get("repository"), dict)
            else item.get("repository"),
            "install": item.get("install") or item.get("packages") or {},
            "capabilities": item.get("capabilities") or item.get("tools") or [],
            "homepage": item.get("homepage") or item.get("url"),
        }
