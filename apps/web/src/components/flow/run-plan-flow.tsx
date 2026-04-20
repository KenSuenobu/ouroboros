"use client";

import { useMemo, useState } from "react";
import {
  Background,
  ReactFlow,
  Controls,
  MiniMap,
  Panel,
  MarkerType,
  type Edge,
  type Node,
  type ReactFlowInstance,
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
  const [hoveredEdge, setHoveredEdge] = useState<{ edgeId: string; x: number; y: number } | null>(null);
  const [showBackground, setShowBackground] = useState(true);
  const [showMiniMap, setShowMiniMap] = useState(false);
  const [showEdgeLabels, setShowEdgeLabels] = useState(true);
  const [edgeShape, setEdgeShape] = useState<"straight" | "step" | "smoothstep" | "bezier">("smoothstep");
  const [viewLocked, setViewLocked] = useState(false);
  const [flowInstance, setFlowInstance] = useState<ReactFlowInstance | null>(null);

  const nodeLabelById = useMemo(
    () =>
      Object.fromEntries((graph.nodes || []).map((node) => [node.id, node.label || node.id])),
    [graph.nodes],
  );

  const edgeInfoById = useMemo(
    () =>
      Object.fromEntries(
        (graph.edges || []).map((edge) => [edge.id, edge]),
      ),
    [graph.edges],
  );

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
        type: edgeShape,
        label: showEdgeLabels ? (e.condition || e.label) : undefined,
        animated: stepStatuses[e.source] === "running",
        style: { stroke: "var(--gray-a8)" },
        markerEnd: { type: MarkerType.ArrowClosed, color: "var(--gray-a8)" },
      })),
    [graph.edges, stepStatuses, showEdgeLabels, edgeShape],
  );

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      fitView
      onInit={setFlowInstance}
      nodesDraggable={!viewLocked}
      elementsSelectable={!viewLocked}
      panOnDrag={!viewLocked}
      zoomOnScroll={!viewLocked}
      zoomOnPinch={!viewLocked}
      zoomOnDoubleClick={!viewLocked}
      onEdgeMouseEnter={(event, edge) =>
        setHoveredEdge({ edgeId: edge.id, x: event.clientX, y: event.clientY })
      }
      onEdgeMouseMove={(event, edge) =>
        setHoveredEdge({ edgeId: edge.id, x: event.clientX, y: event.clientY })
      }
      onEdgeMouseLeave={() => setHoveredEdge(null)}
    >
      {showBackground ? <Background gap={16} /> : null}
      {showMiniMap ? <MiniMap pannable zoomable /> : null}
      <Controls showInteractive={false} />
      <Panel position="top-right">
        <div
          style={{
            display: "grid",
            gap: 6,
            padding: 8,
            borderRadius: 8,
            border: "1px solid var(--gray-a5)",
            background: "var(--gray-a2)",
            fontSize: 12,
            minWidth: 188,
          }}
        >
          <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <input type="checkbox" checked={!viewLocked} onChange={(e) => setViewLocked(!e.target.checked)} />
            Enable pan & zoom
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <input type="checkbox" checked={showBackground} onChange={(e) => setShowBackground(e.target.checked)} />
            Show background grid
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <input type="checkbox" checked={showMiniMap} onChange={(e) => setShowMiniMap(e.target.checked)} />
            Show mini-map
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <input type="checkbox" checked={showEdgeLabels} onChange={(e) => setShowEdgeLabels(e.target.checked)} />
            Show edge labels
          </label>
          <label style={{ display: "grid", gap: 4 }}>
            <span>Edge shape</span>
            <select
              value={edgeShape}
              onChange={(event) =>
                setEdgeShape(event.target.value as "straight" | "step" | "smoothstep" | "bezier")
              }
              style={{
                border: "1px solid var(--gray-a6)",
                borderRadius: 6,
                background: "var(--color-panel-solid)",
                color: "var(--gray-12)",
                padding: "4px 6px",
              }}
            >
              <option value="smoothstep">Smooth step</option>
              <option value="bezier">Bezier</option>
              <option value="step">Step</option>
              <option value="straight">Straight</option>
            </select>
          </label>
          <button
            type="button"
            onClick={() => flowInstance?.fitView({ padding: 0.2 })}
            style={{
              border: "1px solid var(--gray-a6)",
              borderRadius: 6,
              background: "var(--color-panel-solid)",
              color: "var(--gray-12)",
              padding: "4px 8px",
              cursor: "pointer",
            }}
          >
            Re-center view
          </button>
        </div>
      </Panel>
      {hoveredEdge ? (
        <div
          style={{
            position: "fixed",
            left: hoveredEdge.x + 12,
            top: hoveredEdge.y + 12,
            zIndex: 60,
            maxWidth: 280,
            pointerEvents: "none",
            border: "1px solid var(--gray-a6)",
            borderRadius: 8,
            background: "var(--color-panel-solid)",
            color: "var(--gray-12)",
            padding: "8px 10px",
            boxShadow: "0 8px 20px rgba(0, 0, 0, 0.18)",
            fontSize: 12,
            lineHeight: 1.45,
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: 4 }}>Edge details</div>
          <div><strong>From:</strong> {nodeLabelById[edgeInfoById[hoveredEdge.edgeId]?.source || ""] || "?"}</div>
          <div><strong>To:</strong> {nodeLabelById[edgeInfoById[hoveredEdge.edgeId]?.target || ""] || "?"}</div>
          <div><strong>Shape:</strong> {edgeShape}</div>
          <div>
            <strong>Condition:</strong>{" "}
            {edgeInfoById[hoveredEdge.edgeId]?.condition || edgeInfoById[hoveredEdge.edgeId]?.label || "(none)"}
          </div>
          <div><strong>Id:</strong> {hoveredEdge.edgeId}</div>
        </div>
      ) : null}
    </ReactFlow>
  );
}
