"""WebSocket router: per-run live event stream."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..orchestrator.events import bus

router = APIRouter()


@router.websocket("/ws/runs/{run_id}")
async def run_stream(websocket: WebSocket, run_id: str) -> None:
    await websocket.accept()
    queue = bus.subscribe(run_id)
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                await websocket.send_text(json.dumps(event.to_dict(), default=str))
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        pass
    finally:
        bus.unsubscribe(run_id, queue)


@router.websocket("/ws/runs")
async def all_runs_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    queue = bus.subscribe("*")
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                await websocket.send_text(json.dumps(event.to_dict(), default=str))
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        pass
    finally:
        bus.unsubscribe("*", queue)
