"""WebSocket router: per-run live event stream. Authenticated via session cookie or ?token=."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from ..config import settings
from ..db import session as db_session_module
from ..orchestrator.events import bus
from ..services import auth as auth_svc

router = APIRouter()


async def _authenticate_ws(websocket: WebSocket) -> bool:
    token = websocket.cookies.get(settings.auth_session_cookie_name) or websocket.query_params.get(
        "token"
    )
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return False
    async with db_session_module.SessionLocal() as session:
        resolved = await auth_svc.resolve_session(session, token)
        if resolved:
            await session.commit()
    if not resolved:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return False
    return True


@router.websocket("/ws/runs/{run_id}")
async def run_stream(websocket: WebSocket, run_id: str) -> None:
    if not await _authenticate_ws(websocket):
        return
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
    if not await _authenticate_ws(websocket):
        return
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
