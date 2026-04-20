"use client";

import { useEffect, useMemo, useRef } from "react";
import { Box, Text } from "@radix-ui/themes";
import type { RunEvent } from "@/lib/api/types";

const MAX_LOG_LINES = 500;

type LogPaneProps = {
  stepId: string;
  events: RunEvent[];
  isRunning: boolean;
};

export function LogPane({ stepId, events, isRunning }: LogPaneProps) {
  const rows = useMemo(() => {
    const filtered = events.filter((evt) => {
      if (evt.type !== "step.log") return false;
      return evt.payload?.step_id === stepId && typeof evt.payload?.line === "string";
    });
    return filtered.length > MAX_LOG_LINES ? filtered.slice(-MAX_LOG_LINES) : filtered;
  }, [events, stepId]);
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!isRunning) return;
    endRef.current?.scrollIntoView({ block: "end" });
  }, [isRunning, rows.length]);

  return (
    <Box className="rounded-md border border-[var(--gray-a5)] bg-[var(--gray-a2)] p-2">
      <Text size="1" color="gray">
        Live logs
      </Text>
      <div className="mt-1 max-h-44 overflow-auto rounded bg-[var(--gray-1)] p-2 font-mono text-xs">
        {rows.length === 0 ? (
          <Text size="1" color="gray">
            {isRunning ? "Waiting for log output..." : "No live logs for this step."}
          </Text>
        ) : (
          rows.map((evt, i) => {
            const stream = typeof evt.payload.stream === "string" ? evt.payload.stream : "stdout";
            const line = String(evt.payload.line ?? "");
            return (
              <div
                key={`${evt.timestamp}-${i}`}
                className={stream === "stderr" ? "text-red-500" : "text-[var(--gray-12)]"}
              >
                [{stream}] {line}
              </div>
            );
          })
        )}
        <div ref={endRef} />
      </div>
    </Box>
  );
}
