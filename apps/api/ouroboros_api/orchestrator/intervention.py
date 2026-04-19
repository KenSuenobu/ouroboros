"""Async intervention queue: an event per pending question; resolved by REST."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _PendingIntervention:
    intervention_id: str
    event: asyncio.Event = field(default_factory=asyncio.Event)
    answer: dict[str, Any] | None = None


class InterventionRegistry:
    def __init__(self) -> None:
        self._pending: dict[str, _PendingIntervention] = {}
        self._lock = asyncio.Lock()

    async def register(self, intervention_id: str) -> _PendingIntervention:
        async with self._lock:
            entry = _PendingIntervention(intervention_id=intervention_id)
            self._pending[intervention_id] = entry
            return entry

    async def answer(self, intervention_id: str, answer: dict[str, Any]) -> bool:
        async with self._lock:
            entry = self._pending.get(intervention_id)
            if not entry:
                return False
            entry.answer = answer
            entry.event.set()
            return True

    async def wait(self, intervention_id: str, *, timeout: float | None = None) -> dict[str, Any] | None:
        entry = self._pending.get(intervention_id)
        if not entry:
            return None
        try:
            await asyncio.wait_for(entry.event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return None
        return entry.answer

    async def discard(self, intervention_id: str) -> None:
        async with self._lock:
            self._pending.pop(intervention_id, None)


registry = InterventionRegistry()
