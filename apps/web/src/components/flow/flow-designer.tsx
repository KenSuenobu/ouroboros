"use client";

import { useCallback, useMemo, useState } from "react";
import {
  Background,
  Controls,
  ReactFlow,
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  type Connection,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange,
  type NodeProps,
  Handle,
  Position,
} from "@xyflow/react";
import { Box, Button, Flex, Text, TextField } from "@radix-ui/themes";
import type { FlowEdge, FlowNode } from "@/lib/api/types";

interface Props {
  graph: { nodes: FlowNode[]; edges: FlowEdge[] };
  onChange: (graph: { nodes: FlowNode[]; edges: FlowEdge[] }) => void;
}

const NODE_COLOR: Record<string, string> = {
  agent: "var(--iris-a4)",
  wait_for_user: "var(--amber-a4)",
  condition: "var(--violet-a4)",
  parallel: "var(--green-a4)",
};

function AgentNode({ data, id }: NodeProps) {
  return (
    <Box
      style={{
        background: NODE_COLOR[(data?.kind as string) || "agent"],
        border: "1px solid var(--gray-a8)",
        borderRadius: 8,
        padding: 10,
        minWidth: 160,
      }}
    >
      <Handle type="target" position={Position.Left} />
      <Text size="1" color="gray" weight="bold" style={{ textTransform: "uppercase" }}>
        {(data?.kind as string) || "agent"}
      </Text>
      <Text weight="bold" size="2">{(data?.label as string) || id}</Text>
      {data?.role ? <Text size="1" color="gray">{String(data.role)}</Text> : null}
      <Handle type="source" position={Position.Right} />
    </Box>
  );
}

const NODE_TYPES = { custom: AgentNode };

export function FlowDesigner({ graph, onChange }: Props) {
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);

  const nodes: Node[] = useMemo(
    () =>
      graph.nodes.map((n) => ({
        id: n.id,
        type: "custom",
        position: n.position || { x: 0, y: 0 },
        data: { label: n.label, kind: n.type, role: n.agent_role },
      })),
    [graph.nodes],
  );

  const edges: Edge[] = useMemo(
    () =>
      graph.edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        label: e.condition || e.label,
        animated: false,
        style: { stroke: e.id === selectedEdgeId ? "var(--accent-9)" : "var(--gray-a8)" },
      })),
    [graph.edges, selectedEdgeId],
  );

  const handleNodesChange = useCallback(
    (changes: NodeChange[]) => {
      const next = applyNodeChanges(changes, nodes);
      const updated: FlowNode[] = next.map((node) => {
        const original = graph.nodes.find((n) => n.id === node.id);
        return {
          ...(original || {
            id: node.id,
            type: "agent",
            label: String(node.data?.label || node.id),
            position: node.position,
          }),
          position: node.position,
        };
      });
      onChange({ nodes: updated, edges: graph.edges });
    },
    [graph, nodes, onChange],
  );

  const handleEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      const next = applyEdgeChanges(changes, edges);
      const surviving = new Set(next.map((e) => e.id));
      onChange({
        nodes: graph.nodes,
        edges: graph.edges.filter((e) => surviving.has(e.id)),
      });
    },
    [edges, graph, onChange],
  );

  const handleConnect = useCallback(
    (connection: Connection) => {
      if (!connection.source || !connection.target) return;
      const newEdges = addEdge(connection, edges);
      const newSlim = newEdges.find((e) => !graph.edges.some((g) => g.id === e.id));
      if (!newSlim) return;
      onChange({
        nodes: graph.nodes,
        edges: [
          ...graph.edges,
          { id: newSlim.id, source: newSlim.source!, target: newSlim.target!, condition: "" },
        ],
      });
    },
    [edges, graph, onChange],
  );

  const updateEdgeCondition = (edgeId: string, condition: string) => {
    onChange({
      nodes: graph.nodes,
      edges: graph.edges.map((e) => (e.id === edgeId ? { ...e, condition } : e)),
    });
  };

  return (
    <Flex direction="column" style={{ height: "100%" }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={NODE_TYPES}
        onNodesChange={handleNodesChange}
        onEdgesChange={handleEdgesChange}
        onConnect={handleConnect}
        onEdgeClick={(_, edge) => setSelectedEdgeId(edge.id)}
        fitView
      >
        <Background gap={16} />
        <Controls />
      </ReactFlow>
      {selectedEdgeId ? (
        <Flex
          gap="2"
          align="center"
          style={{
            borderTop: "1px solid var(--gray-a5)",
            padding: 8,
            background: "var(--gray-a2)",
          }}
        >
          <Text size="2" weight="bold">Edge condition</Text>
          <TextField.Root
            style={{ flex: 1 }}
            placeholder="e.g. tests.failed && attempt < 3"
            value={graph.edges.find((e) => e.id === selectedEdgeId)?.condition || ""}
            onChange={(e) => updateEdgeCondition(selectedEdgeId, e.target.value)}
          />
          <Button size="1" variant="soft" onClick={() => setSelectedEdgeId(null)}>Done</Button>
        </Flex>
      ) : null}
    </Flex>
  );
}
