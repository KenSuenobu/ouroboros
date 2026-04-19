"""In-process pub/sub for run events. WebSockets attach as subscribers."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class RunEvent:
    run_id: str
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RunEventBus:
    def __init__(self) -> None:
        self._queues: dict[str, set[asyncio.Queue[RunEvent]]] = defaultdict(set)
        self._history: dict[str, list[RunEvent]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def publish(self, event: RunEvent) -> None:
        async with self._lock:
            self._history[event.run_id].append(event)
            for q in list(self._queues[event.run_id]):
                try:
                    q.put_nowait(event)
                except asyncio.QueueFull:
                    pass
            for q in list(self._queues["*"]):
                try:
                    q.put_nowait(event)
                except asyncio.QueueFull:
                    pass

    def subscribe(self, run_id: str = "*") -> asyncio.Queue[RunEvent]:
        q: asyncio.Queue[RunEvent] = asyncio.Queue(maxsize=2000)
        self._queues[run_id].add(q)
        for past in self._history.get(run_id, []):
            try:
                q.put_nowait(past)
            except asyncio.QueueFull:
                break
        return q

    def unsubscribe(self, run_id: str, q: asyncio.Queue[RunEvent]) -> None:
        self._queues[run_id].discard(q)

    def history(self, run_id: str) -> list[RunEvent]:
        return list(self._history.get(run_id, []))


bus = RunEventBus()
