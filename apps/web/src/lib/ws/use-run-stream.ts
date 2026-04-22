"use client";

import { useEffect, useRef, useState } from "react";
import type { RunEvent } from "../api/types";
import { getActiveServer, LOCAL_SERVER_ID } from "../servers/registry";

function buildWsUrl(path: string): string {
  const active = getActiveServer();
  if (active.id === LOCAL_SERVER_ID || active.url === "local") {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${window.location.host}${path}`;
  }
  // Remote server: connect directly. The browser cannot share the HttpOnly
  // session cookie cross-origin, so live run streams are best-effort here
  // and may require the operator to allow cross-origin WS or to expose a
  // session token. Until that lands, the connection will simply fail-closed
  // and the run page falls back to polling REST endpoints.
  const base = active.url.replace(/^http/i, (m) => (m.toLowerCase() === "https" ? "wss" : "ws"));
  return `${base}${path}`;
}

export function useRunStream(runId: string | null) {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!runId) return;
    setEvents([]);
    const url = buildWsUrl(`/ws/runs/${runId}`);
    const socket = new WebSocket(url);
    wsRef.current = socket;
    socket.onopen = () => setConnected(true);
    socket.onclose = () => setConnected(false);
    socket.onmessage = (msg) => {
      try {
        const parsed = JSON.parse(msg.data) as RunEvent | { type: "ping" };
        if ("type" in parsed && parsed.type === "ping") return;
        setEvents((current) => [...current, parsed as RunEvent]);
      } catch {
        /* ignore */
      }
    };
    return () => {
      socket.close();
      wsRef.current = null;
    };
  }, [runId]);

  return { events, connected };
}
