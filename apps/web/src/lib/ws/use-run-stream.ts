"use client";

import { useEffect, useRef, useState } from "react";
import type { RunEvent } from "../api/types";

export function useRunStream(runId: string | null) {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!runId) return;
    setEvents([]);
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${proto}//${window.location.host}/ws/runs/${runId}`;
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
