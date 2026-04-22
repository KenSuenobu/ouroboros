"use client";

import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { mutate } from "swr";
import { Badge, Box, Button, Flex, Heading, Select, Text, TextField } from "@radix-ui/themes";
import { PageShell, PageHeader } from "@/components/layout/page-shell";
import { SidebarList } from "@/components/common/sidebar-list";
import { useAgents, useFlows } from "@/lib/api/hooks";
import { api } from "@/lib/api/client";
import type { Flow, FlowEdge, FlowNode } from "@/lib/api/types";
import { RequireAdmin } from "@/lib/auth/guards";

const FlowDesigner = dynamic(() => import("@/components/flow/flow-designer").then((m) => m.FlowDesigner), { ssr: false });

const EMPTY_GRAPH = { nodes: [] as FlowNode[], edges: [] as FlowEdge[] };

export default function RoutingPage() {
  return (
    <RequireAdmin
      fallback={
        <PageShell sidebar={<div />}>
          <PageHeader title="Routing" />
          <Box p="5">
            <Heading size="4" mb="2">Admins only</Heading>
            <Text size="2" color="gray">
              You need admin access in this workspace to manage flows and routing.
            </Text>
          </Box>
        </PageShell>
      }
    >
      <RoutingPageInner />
    </RequireAdmin>
  );
}

function RoutingPageInner() {
  const { data: flows = [] } = useFlows();
  const { data: agents = [] } = useAgents();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [draft, setDraft] = useState<{ name: string; description: string; graph: Flow["graph"]; is_default: boolean } | null>(null);

  const active = activeId ? flows.find((f) => f.id === activeId) ?? null : null;

  useEffect(() => {
    if (active) {
      setDraft({
        name: active.name,
        description: active.description || "",
        graph: active.graph || EMPTY_GRAPH,
        is_default: active.is_default,
      });
    } else if (!flows.length) {
      setDraft({ name: "", description: "", graph: EMPTY_GRAPH, is_default: false });
    }
  }, [active?.id, flows.length]);

  const startNew = () => {
    setActiveId(null);
    setDraft({ name: "", description: "", graph: EMPTY_GRAPH, is_default: false });
  };

  const save = async () => {
    if (!draft) return;
    if (active) {
      await api.put(`/api/flows/${active.id}`, draft);
    } else {
      const created = await api.post<Flow>("/api/flows", draft);
      setActiveId(created.id);
    }
    await mutate("/api/flows");
  };

  const remove = async () => {
    if (!active) return;
    await api.del(`/api/flows/${active.id}`);
    setActiveId(null);
    await mutate("/api/flows");
  };

  return (
    <PageShell
      sidebar={
        <SidebarList
          title="Flows"
          items={flows.map((f) => ({
            id: f.id,
            primary: f.name,
            secondary: f.description || `${(f.graph?.nodes || []).length} nodes`,
            badge: f.is_default ? <Badge color="iris">default</Badge> : null,
          }))}
          activeId={activeId}
          onSelect={setActiveId}
          onAdd={startNew}
        />
      }
    >
      <PageHeader
        title={active?.name || (draft ? "New flow" : "Routing")}
        subtitle={
          draft
            ? "Drop agent + control nodes onto the canvas. Edges can carry conditions like `tests.failed && attempt < 3`."
            : "Pick a flow to edit, or create one."
        }
        actions={
          draft ? (
            <Flex gap="2">
              {active && !active.is_default ? (
                <Button color="red" variant="soft" onClick={remove}>Delete</Button>
              ) : null}
              <Button onClick={save}>{active ? "Save" : "Create"}</Button>
            </Flex>
          ) : null
        }
      />
      {draft ? (
        <Flex direction="column" gap="3">
          <Flex gap="3" wrap="wrap" align="center">
            <Box style={{ flex: "1 1 200px" }}>
              <Field label="Name">
                <TextField.Root value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
              </Field>
            </Box>
            <Box style={{ flex: "2 1 320px" }}>
              <Field label="Description">
                <TextField.Root value={draft.description} onChange={(e) => setDraft({ ...draft, description: e.target.value })} />
              </Field>
            </Box>
            <Flex align="center" gap="2">
              <input
                type="checkbox"
                checked={draft.is_default}
                onChange={(e) => setDraft({ ...draft, is_default: e.target.checked })}
              />
              <Text size="2">Default flow</Text>
            </Flex>
          </Flex>
          <NodePalette
            agents={agents.map((a) => ({ role: a.role, name: a.name }))}
            onAddNode={(node) =>
              setDraft({
                ...draft,
                graph: {
                  ...draft.graph,
                  nodes: [...(draft.graph.nodes || []), node],
                },
              })
            }
          />
          <div className="flow-wrapper">
            <FlowDesigner graph={draft.graph} onChange={(graph) => setDraft({ ...draft, graph })} />
          </div>
        </Flex>
      ) : (
        <div className="empty-state">Select or create a flow</div>
      )}
    </PageShell>
  );
}

function NodePalette({ agents, onAddNode }: { agents: Array<{ role: string; name: string }>; onAddNode: (n: FlowNode) => void }) {
  const [agentRole, setAgentRole] = useState(agents[0]?.role || "");

  const addAgent = () => {
    if (!agentRole) return;
    const id = `${agentRole}-${Math.random().toString(36).slice(2, 7)}`;
    onAddNode({
      id,
      type: "agent",
      agent_role: agentRole,
      label: agents.find((a) => a.role === agentRole)?.name || agentRole,
      position: { x: 100 + Math.random() * 200, y: 100 + Math.random() * 200 },
    });
  };

  const addControl = (type: FlowNode["type"]) => {
    const id = `${type}-${Math.random().toString(36).slice(2, 7)}`;
    onAddNode({
      id,
      type,
      label: type,
      position: { x: 200 + Math.random() * 200, y: 200 + Math.random() * 200 },
    });
  };

  return (
    <Flex gap="2" wrap="wrap" align="center" style={{ background: "var(--gray-a2)", padding: 8, borderRadius: 8 }}>
      <Text size="2" weight="bold">Add node:</Text>
      <Select.Root value={agentRole} onValueChange={setAgentRole}>
        <Select.Trigger />
        <Select.Content>
          {agents.map((a) => (
            <Select.Item key={a.role} value={a.role}>{a.name}</Select.Item>
          ))}
        </Select.Content>
      </Select.Root>
      <Button size="1" variant="soft" onClick={addAgent}>+ Agent</Button>
      <Button size="1" variant="soft" onClick={() => addControl("wait_for_user")}>+ Wait for user</Button>
      <Button size="1" variant="soft" onClick={() => addControl("condition")}>+ Condition</Button>
      <Button size="1" variant="soft" onClick={() => addControl("parallel")}>+ Parallel</Button>
    </Flex>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <Flex direction="column" gap="1">
      <Text size="2" color="gray" weight="medium">{label}</Text>
      {children}
    </Flex>
  );
}
