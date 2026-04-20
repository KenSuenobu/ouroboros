"use client";

import { useEffect, useState } from "react";
import { mutate } from "swr";
import {
  Badge,
  Box,
  Button,
  Flex,
  Select,
  Text,
  TextField,
} from "@radix-ui/themes";
import { PageShell, PageHeader } from "@/components/layout/page-shell";
import { SidebarList } from "@/components/common/sidebar-list";
import { useProviderModels, useProviders } from "@/lib/api/hooks";
import { api } from "@/lib/api/client";
import type { Provider, ProviderHealth, ProviderInput } from "@/lib/api/types";

const KINDS: Array<Provider["kind"]> = ["ollama", "anthropic", "github_models", "opencode", "gh_copilot"];

const DEFAULT_BASE_URL: Record<string, string> = {
  ollama: "http://localhost:11434",
  anthropic: "https://api.anthropic.com",
  github_models: "https://models.github.ai",
};

const HEALTH_LABEL: Record<NonNullable<Provider["last_health_status"]>, string> = {
  ok: "ok",
  unreachable: "unreachable",
  unauthorized: "unauthorized",
  "no-models": "no models",
};

const HEALTH_COLOR: Record<NonNullable<Provider["last_health_status"]>, "green" | "red" | "orange" | "gray"> = {
  ok: "green",
  unreachable: "red",
  unauthorized: "orange",
  "no-models": "gray",
};

export default function ProvidersPage() {
  const { data: providers = [] } = useProviders();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [draft, setDraft] = useState<ProviderInput | null>(null);
  const [healthInfo, setHealthInfo] = useState<string | null>(null);
  const [showHealthDetails, setShowHealthDetails] = useState(false);
  const [refreshingHealth, setRefreshingHealth] = useState(false);

  const active = activeId ? providers.find((p) => p.id === activeId) ?? null : null;

  useEffect(() => {
    if (active) {
      setDraft({
        name: active.name,
        kind: active.kind,
        base_url: active.base_url,
        config: active.config,
        enabled: active.enabled,
      });
      setHealthInfo(active.last_health_error);
      setShowHealthDetails(false);
    }
  }, [active?.id]);

  const startNew = () => {
    setActiveId(null);
    setDraft({
      name: "",
      kind: "ollama",
      base_url: DEFAULT_BASE_URL.ollama,
      config: {},
      enabled: true,
    });
  };

  const save = async () => {
    if (!draft) return;
    if (active) {
      await api.put(`/api/providers/${active.id}`, draft);
    } else {
      const created = await api.post<Provider>("/api/providers", draft);
      setActiveId(created.id);
    }
    await mutate("/api/providers");
  };

  const remove = async () => {
    if (!active) return;
    await api.del(`/api/providers/${active.id}`);
    setActiveId(null);
    setDraft(null);
    await mutate("/api/providers");
  };

  const refreshHealth = async () => {
    if (!active) return;
    setRefreshingHealth(true);
    try {
      const res = await api.get<ProviderHealth>(`/api/providers/${active.id}/health`);
      setHealthInfo(res.error);
      setShowHealthDetails(false);
      await mutate("/api/providers");
    } finally {
      setRefreshingHealth(false);
    }
  };

  return (
    <PageShell
      sidebar={
        <SidebarList
          title="Providers"
          items={providers.map((p) => ({
            id: p.id,
            primary: p.name,
            secondary: p.kind,
            badge: <HealthBadge provider={p} />,
          }))}
          activeId={activeId}
          onSelect={setActiveId}
          onAdd={startNew}
        />
      }
    >
      <PageHeader
        title={active?.name || (draft ? "New provider" : "Providers")}
        subtitle={active?.kind || (draft ? "Connect a provider and test it" : "Pick a provider")}
        actions={
          draft ? (
            <Flex gap="2">
              {active ? (
                <Button variant="soft" onClick={refreshHealth} disabled={refreshingHealth}>
                  {refreshingHealth ? "Refreshing..." : "Refresh health"}
                </Button>
              ) : null}
              {active ? (
                <Button color="red" variant="soft" onClick={remove}>Delete</Button>
              ) : null}
              <Button onClick={save}>{active ? "Save" : "Create"}</Button>
            </Flex>
          ) : null
        }
      />
      {draft ? (
        <Flex gap="4" wrap="wrap">
          <Box style={{ minWidth: 380, flex: 1 }}>
            <Flex direction="column" gap="3">
              <Field label="Name">
                <TextField.Root value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
              </Field>
              <Field label="Kind">
                <Select.Root
                  value={draft.kind}
                  onValueChange={(v) =>
                    setDraft({
                      ...draft,
                      kind: v as Provider["kind"],
                      base_url: DEFAULT_BASE_URL[v] || draft.base_url,
                    })
                  }
                >
                  <Select.Trigger />
                  <Select.Content>
                    {KINDS.map((k) => (
                      <Select.Item key={k} value={k}>{k}</Select.Item>
                    ))}
                  </Select.Content>
                </Select.Root>
              </Field>
              <Field label="Base URL">
                <TextField.Root
                  value={draft.base_url || ""}
                  onChange={(e) => setDraft({ ...draft, base_url: e.target.value || null })}
                />
              </Field>
              <Field label="API key (write-only)">
                <TextField.Root
                  type="password"
                  placeholder={active?.has_api_key ? "(stored - leave blank to keep)" : "paste secret"}
                  onChange={(e) => setDraft({ ...draft, api_key: e.target.value || undefined })}
                />
              </Field>
              <Flex gap="2" align="center">
                <input
                  type="checkbox"
                  checked={draft.enabled}
                  onChange={(e) => setDraft({ ...draft, enabled: e.target.checked })}
                />
                <Text size="2">Enabled</Text>
              </Flex>
              {active ? (
                <Field label="Health">
                  <Flex direction="column" gap="1">
                    <HealthBadge provider={active} onClick={() => setShowHealthDetails((v) => !v)} />
                    {showHealthDetails ? (
                      <Box style={{ border: "1px solid var(--gray-a6)", borderRadius: 8, padding: 8 }}>
                        <Text size="1">{healthInfo || "No error reported by the last health probe."}</Text>
                      </Box>
                    ) : null}
                  </Flex>
                </Field>
              ) : null}
              {active && ["ollama", "anthropic", "github_models"].includes(active.kind) ? (
                <ProviderModelsPanel providerId={active.id} />
              ) : null}
            </Flex>
          </Box>
          {active && ["ollama", "anthropic", "github_models"].includes(active.kind) ? (
            <Box style={{ minWidth: 420, flex: 1 }}>
              <ChatTester providerId={active.id} />
            </Box>
          ) : null}
        </Flex>
      ) : (
        <div className="empty-state">Select or create a provider</div>
      )}
    </PageShell>
  );
}

function HealthBadge({ provider, onClick }: { provider: Provider; onClick?: () => void }) {
  const status = provider.last_health_status;
  const badge = !status ? (
    <Badge color="gray" title="No health check yet">
      unknown
    </Badge>
  ) : (
    <Badge color={HEALTH_COLOR[status]} title={provider.last_health_error || ""}>
      {HEALTH_LABEL[status]}
    </Badge>
  );

  if (!onClick) return badge;

  return (
    <button
      type="button"
      onClick={onClick}
      style={{ background: "transparent", border: 0, padding: 0, margin: 0, cursor: "pointer" }}
    >
      {badge}
    </button>
  );
}

function ProviderModelsPanel({ providerId }: { providerId: string }) {
  const { data: models = [] } = useProviderModels(providerId);
  const refresh = async () => {
    await api.post(`/api/providers/${providerId}/models/refresh`);
    await mutate(`/api/providers/${providerId}/models`);
  };
  return (
    <Field label={`Models (${models.length})`}>
      <Flex direction="column" gap="2">
        <Button variant="soft" onClick={refresh}>Refresh from provider</Button>
        <Flex direction="column" gap="1" style={{ maxHeight: 200, overflow: "auto" }}>
          {models.map((m) => (
            <Flex key={m.id} align="center" justify="between">
              <Text size="2">{m.display_name || m.model_id}</Text>
              <Text size="1" color="gray">{m.context_window || ""}</Text>
            </Flex>
          ))}
        </Flex>
      </Flex>
    </Field>
  );
}

function ChatTester({ providerId }: { providerId: string }) {
  const { data: models = [] } = useProviderModels(providerId);
  const [model, setModel] = useState<string | null>(null);
  const [messages, setMessages] = useState<Array<{ role: string; content: string }>>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!model && models.length) setModel(models[0].model_id);
  }, [models, model]);

  const send = async () => {
    if (!input || !model) return;
    const next = [...messages, { role: "user", content: input }];
    setMessages(next);
    setInput("");
    setBusy(true);
    try {
      const res = await api.post<{ content: string }>(`/api/providers/${providerId}/chat`, {
        model_id: model,
        messages: next,
        max_tokens: 1024,
      });
      setMessages([...next, { role: "assistant", content: res.content }]);
    } catch (err) {
      setMessages([...next, { role: "assistant", content: `error: ${String(err)}` }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Box style={{ border: "1px solid var(--gray-a5)", borderRadius: 8, padding: 12 }}>
      <Flex justify="between" align="center" mb="2">
        <Text weight="bold">Chat tester</Text>
        <Select.Root value={model || ""} onValueChange={setModel}>
          <Select.Trigger />
          <Select.Content>
            {models.map((m) => (
              <Select.Item key={m.id} value={m.model_id}>{m.display_name || m.model_id}</Select.Item>
            ))}
          </Select.Content>
        </Select.Root>
      </Flex>
      <Box style={{ height: 320, overflow: "auto", padding: 8, background: "var(--gray-a2)", borderRadius: 6 }}>
        {messages.length === 0 ? <Text size="2" color="gray">Send a message to test the provider.</Text> : null}
        {messages.map((m, i) => (
          <Box
            key={i}
            mb="2"
            style={{
              padding: 8,
              borderRadius: 6,
              background: m.role === "user" ? "var(--iris-a3)" : "var(--gray-a3)",
            }}
          >
            <Text size="1" color="gray" weight="bold">{m.role}</Text>
            <pre style={{ whiteSpace: "pre-wrap", margin: 0, fontSize: 13 }}>{m.content}</pre>
          </Box>
        ))}
      </Box>
      <Flex gap="2" mt="2">
        <TextField.Root
          style={{ flex: 1 }}
          placeholder="Type and press send"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
        />
        <Button onClick={send} disabled={busy}>{busy ? "..." : "Send"}</Button>
      </Flex>
    </Box>
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
