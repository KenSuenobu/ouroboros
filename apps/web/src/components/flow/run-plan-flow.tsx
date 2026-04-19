"use client";

import { useMemo } from "react";
import {
  Background,
  ReactFlow,
  Controls,
  type Edge,
  type Node,
} from "@xyflow/react";
import type { FlowEdge, FlowNode } from "@/lib/api/types";

interface Props {
  graph: { nodes?: FlowNode[]; edges?: FlowEdge[] };
  stepStatuses: Record<string, string>;
}

const STATUS_BG: Record<string, string> = {
  pending: "var(--gray-a4)",
  running: "var(--iris-a5)",
  succeeded: "var(--green-a5)",
  failed: "var(--red-a5)",
  cancelled: "var(--amber-a5)",
};

const STATUS_BORDER: Record<string, string> = {
  pending: "var(--gray-a8)",
  running: "var(--iris-a9)",
  succeeded: "var(--green-a9)",
  failed: "var(--red-a9)",
  cancelled: "var(--amber-a9)",
};

export function RunPlanFlow({ graph, stepStatuses }: Props) {
  const nodes: Node[] = useMemo(
    () =>
      (graph.nodes || []).map((n) => {
        const status = stepStatuses[n.id] || "pending";
        return {
          id: n.id,
          position: n.position || { x: 0, y: 0 },
          data: { label: n.label || n.id },
          style: {
            background: STATUS_BG[status],
            border: `1px solid ${STATUS_BORDER[status]}`,
            color: "var(--gray-12)",
            padding: 8,
            borderRadius: 8,
            minWidth: 160,
            fontSize: 13,
          },
        };
      }),
    [graph.nodes, stepStatuses],
  );

  const edges: Edge[] = useMemo(
    () =>
      (graph.edges || []).map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        label: e.condition || e.label,
        animated: stepStatuses[e.source] === "running",
        style: { stroke: "var(--gray-a8)" },
      })),
    [graph.edges, stepStatuses],
  );

  return (
    <ReactFlow nodes={nodes} edges={edges} fitView nodesDraggable={false}>
      <Background gap={16} />
      <Controls showInteractive={false} />
    </ReactFlow>
  );
}
