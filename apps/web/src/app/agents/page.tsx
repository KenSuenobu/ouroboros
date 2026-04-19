"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import {
  Badge,
  Box,
  Button,
  Flex,
  Select,
  Tabs,
  Text,
  TextArea,
  TextField,
} from "@radix-ui/themes";
import { mutate } from "swr";
import { PageShell, PageHeader } from "@/components/layout/page-shell";
import { SidebarList } from "@/components/common/sidebar-list";
import { useAgents, useProviders } from "@/lib/api/hooks";
import { api } from "@/lib/api/client";
import type { Agent, AgentInput } from "@/lib/api/types";

const MonacoPrompt = dynamic(() => import("@/components/editors/prompt-editor").then((m) => m.PromptEditor), { ssr: false });

const ADAPTERS = [
  "builtin",
  "anthropic_api",
  "ollama_api",
  "github_models_api",
  "opencode_cli",
  "gh_copilot_cli",
];

const EMPTY: AgentInput = {
  name: "",
  role: "",
  description: "",
  system_prompt: "",
  execution_adapter: "anthropic_api",
  model_policy: { kind: "router" },
  config: {},
  dry_run_default: false,
  tool_bindings: [],
};

export default function AgentsPage() {
  const { data: agents = [] } = useAgents();
  const { data: providers = [] } = useProviders();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [draft, setDraft] = useState<AgentInput | null>(null);

  const active = activeId ? agents.find((a) => a.id === activeId) ?? null : null;

  useEffect(() => {
    if (active) {
      setDraft({
        name: active.name,
        role: active.role,
        description: active.description || "",
        system_prompt: active.system_prompt,
        execution_adapter: active.execution_adapter,
        model_policy: active.model_policy,
        config: active.config,
        dry_run_default: active.dry_run_default,
        tool_bindings: active.tool_bindings,
      });
    } else {
      setDraft(null);
    }
  }, [active?.id]);

  const startNew = () => {
    setActiveId(null);
    setDraft({ ...EMPTY });
  };

  const save = async () => {
    if (!draft) return;
    if (active) {
      await api.put(`/api/agents/${active.id}`, draft);
    } else {
      const created = await api.post<Agent>("/api/agents", draft);
      setActiveId(created.id);
    }
    await mutate("/api/agents");
  };

  const remove = async () => {
    if (!active) return;
    await api.del(`/api/agents/${active.id}`);
    setActiveId(null);
    setDraft(null);
    await mutate("/api/agents");
  };

  return (
    <PageShell
      sidebar={
        <SidebarList
          title="Agents"
          items={agents.map((a) => ({
            id: a.id,
            primary: a.name,
            secondary: a.role,
            badge: a.is_builtin ? <Badge color="gray" variant="soft">built-in</Badge> : null,
          }))}
          activeId={activeId}
          onSelect={setActiveId}
          onAdd={startNew}
        />
      }
    >
      <PageHeader
        title={active?.name || (draft ? "New agent" : "Agents")}
        subtitle={active?.role || (draft ? "Configure adapter, model policy, and tools" : "Pick an agent to edit")}
        actions={
          draft ? (
            <Flex gap="2">
              {active && !active.is_builtin ? (
                <Button color="red" variant="soft" onClick={remove}>Delete</Button>
              ) : null}
              <Button onClick={save}>{active ? "Save" : "Create"}</Button>
            </Flex>
          ) : null
        }
      />
      {draft ? (
        <Tabs.Root defaultValue="prompt">
          <Tabs.List>
            <Tabs.Trigger value="prompt">System prompt</Tabs.Trigger>
            <Tabs.Trigger value="execution">Execution</Tabs.Trigger>
            <Tabs.Trigger value="tools">Tool bindings</Tabs.Trigger>
            <Tabs.Trigger value="test">Test (dry-run)</Tabs.Trigger>
          </Tabs.List>
          <Box mt="3">
            <Tabs.Content value="prompt">
              <Flex direction="column" gap="3" maxWidth="900px">
                <Flex gap="3">
                  <Field label="Name" style={{ flex: 1 }}>
                    <TextField.Root value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
                  </Field>
                  <Field label="Role" style={{ flex: 1 }}>
                    <TextField.Root value={draft.role} onChange={(e) => setDraft({ ...draft, role: e.target.value })} />
                  </Field>
                </Flex>
                <Field label="Description">
                  <TextField.Root value={draft.description || ""} onChange={(e) => setDraft({ ...draft, description: e.target.value })} />
                </Field>
                <Field label="System prompt (Markdown supported)">
                  <Box style={{ height: 360, border: "1px solid var(--gray-a5)", borderRadius: 8 }}>
                    <MonacoPrompt
                      value={draft.system_prompt}
                      onChange={(value) => setDraft({ ...draft, system_prompt: value })}
                    />
                  </Box>
                </Field>
              </Flex>
            </Tabs.Content>

            <Tabs.Content value="execution">
              <Flex direction="column" gap="3" maxWidth="640px">
                <Field label="Execution adapter">
                  <Select.Root
                    value={draft.execution_adapter}
                    onValueChange={(v) => setDraft({ ...draft, execution_adapter: v })}
                  >
                    <Select.Trigger />
                    <Select.Content>
                      {ADAPTERS.map((a) => (
                        <Select.Item key={a} value={a}>{a}</Select.Item>
                      ))}
                    </Select.Content>
                  </Select.Root>
                </Field>
                <Field label="Model policy">
                  <Select.Root
                    value={draft.model_policy.kind}
                    onValueChange={(v) =>
                      setDraft({ ...draft, model_policy: { ...draft.model_policy, kind: v as "fixed" | "router" | "user_pick" } })
                    }
                  >
                    <Select.Trigger />
                    <Select.Content>
                      <Select.Item value="router">router (suggested per task)</Select.Item>
                      <Select.Item value="fixed">fixed</Select.Item>
                      <Select.Item value="user_pick">user_pick (ask each run)</Select.Item>
                    </Select.Content>
                  </Select.Root>
                </Field>
                {draft.model_policy.kind === "fixed" ? (
                  <Field label="Fixed provider">
                    <Select.Root
                      value={draft.model_policy.fixed_provider_id || ""}
                      onValueChange={(v) =>
                        setDraft({ ...draft, model_policy: { ...draft.model_policy, fixed_provider_id: v } })
                      }
                    >
                      <Select.Trigger />
                      <Select.Content>
                        {providers.map((p) => (
                          <Select.Item key={p.id} value={p.id}>
                            {p.name} ({p.kind})
                          </Select.Item>
                        ))}
                      </Select.Content>
                    </Select.Root>
                  </Field>
                ) : null}
                <Flex gap="2" align="center">
                  <input
                    type="checkbox"
                    checked={draft.dry_run_default}
                    onChange={(e) => setDraft({ ...draft, dry_run_default: e.target.checked })}
                  />
                  <Text size="2">Default this agent to dry-run mode</Text>
                </Flex>
                <Field label="Config (JSON)">
                  <TextArea
                    rows={8}
                    value={JSON.stringify(draft.config || {}, null, 2)}
                    onChange={(e) => {
                      try {
                        setDraft({ ...draft, config: JSON.parse(e.target.value || "{}") });
                      } catch {
                        /* ignore */
                      }
                    }}
                  />
                </Field>
              </Flex>
            </Tabs.Content>

            <Tabs.Content value="tools">
              <Flex direction="column" gap="2" maxWidth="640px">
                {draft.tool_bindings.length === 0 ? (
                  <Text color="gray" size="2">No tool bindings yet. Built-in tools (read_file, write_file, run_shell) are always available.</Text>
                ) : null}
                {draft.tool_bindings.map((b, i) => (
                  <Flex key={i} gap="2" align="center">
                    <Text size="2">{b.tool_kind}</Text>
                    <Text size="2" color="gray">{b.tool_ref}</Text>
                    <Button
                      size="1"
                      variant="soft"
                      color="red"
                      onClick={() =>
                        setDraft({
                          ...draft,
                          tool_bindings: draft.tool_bindings.filter((_, idx) => idx !== i),
                        })
                      }
                    >
                      Remove
                    </Button>
                  </Flex>
                ))}
                <Button
                  variant="soft"
                  onClick={() =>
                    setDraft({
                      ...draft,
                      tool_bindings: [...draft.tool_bindings, { tool_kind: "mcp", tool_ref: "", config: {} }],
                    })
                  }
                >
                  + Add tool binding
                </Button>
              </Flex>
            </Tabs.Content>

            <Tabs.Content value="test">
              {active ? <AgentTestPanel agentId={active.id} /> : <Text color="gray">Save the agent first.</Text>}
            </Tabs.Content>
          </Box>
        </Tabs.Root>
      ) : (
        <div className="empty-state">Select or create an agent</div>
      )}
    </PageShell>
  );
}

function AgentTestPanel({ agentId }: { agentId: string }) {
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ output: string; tokens_in: number; tokens_out: number; warnings: string[] } | null>(null);

  const run = async () => {
    setBusy(true);
    setResult(null);
    try {
      const res = await api.post<typeof result>(`/api/agents/${agentId}/test`, { input_text: input, dry_run: true });
      setResult(res);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Flex direction="column" gap="3" maxWidth="900px">
      <Field label="Scratch input">
        <TextArea rows={6} value={input} onChange={(e) => setInput(e.target.value)} />
      </Field>
      <Flex gap="2">
        <Button onClick={run} disabled={busy}>{busy ? "Running..." : "Run dry-run test"}</Button>
        <Badge color="amber" variant="soft">dry-run · no persistence</Badge>
      </Flex>
      {result ? (
        <Box style={{ background: "var(--gray-a2)", padding: 12, borderRadius: 8 }}>
          <Text size="2" color="gray">
            tokens in/out: {result.tokens_in}/{result.tokens_out}
          </Text>
          <pre style={{ whiteSpace: "pre-wrap", fontSize: 13 }}>{result.output}</pre>
          {result.warnings.length ? (
            <Box mt="2">
              {result.warnings.map((w, i) => (
                <Badge key={i} color="amber" variant="soft" style={{ marginRight: 6 }}>{w}</Badge>
              ))}
            </Box>
          ) : null}
        </Box>
      ) : null}
    </Flex>
  );
}

function Field({
  label,
  children,
  style,
}: {
  label: string;
  children: React.ReactNode;
  style?: React.CSSProperties;
}) {
  return (
    <Flex direction="column" gap="1" style={style}>
      <Text size="2" color="gray" weight="medium">{label}</Text>
      {children}
    </Flex>
  );
}
