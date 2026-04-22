"use client";

import { useState } from "react";
import { mutate } from "swr";
import {
  Badge,
  Box,
  Button,
  Flex,
  Heading,
  Tabs,
  Text,
  TextArea,
  TextField,
} from "@radix-ui/themes";
import { Search } from "lucide-react";
import { PageShell, PageHeader } from "@/components/layout/page-shell";
import { SidebarList } from "@/components/common/sidebar-list";
import { useMcpRegistry, useMcpServers } from "@/lib/api/hooks";
import { api } from "@/lib/api/client";
import type { McpServer } from "@/lib/api/types";
import { RequireAdmin } from "@/lib/auth/guards";

export default function McpPage() {
  return (
    <RequireAdmin
      fallback={
        <PageShell sidebar={<div />}>
          <PageHeader title="MCP" />
          <Box p="5">
            <Heading size="4" mb="2">Admins only</Heading>
            <Text size="2" color="gray">
              You need admin access in this workspace to manage MCP servers.
            </Text>
          </Box>
        </PageShell>
      }
    >
      <McpPageInner />
    </RequireAdmin>
  );
}

function McpPageInner() {
  const [query, setQuery] = useState("");
  const { data: registry = [] } = useMcpRegistry(query);
  const { data: installed = [] } = useMcpServers();
  const [activeServerId, setActiveServerId] = useState<string | null>(null);

  return (
    <PageShell
      sidebar={
        <Flex direction="column" gap="3">
          <Text size="1" color="gray" weight="bold" style={{ textTransform: "uppercase" }}>Installed</Text>
          <SidebarList
            items={installed.map((s) => ({
              id: s.id,
              primary: s.name,
              secondary: s.transport,
              badge: s.side_effecting ? <Badge color="amber" variant="soft">side-effects</Badge> : null,
            }))}
            activeId={activeServerId}
            onSelect={setActiveServerId}
            emptyLabel="No installed servers"
          />
        </Flex>
      }
    >
      <PageHeader
        title="MCP"
        subtitle="Browse the registry, install servers locally, test their tools"
      />
      <Tabs.Root defaultValue="registry">
        <Tabs.List>
          <Tabs.Trigger value="registry">Registry</Tabs.Trigger>
          <Tabs.Trigger value="installed">Installed</Tabs.Trigger>
        </Tabs.List>
        <Box mt="3">
          <Tabs.Content value="registry">
            <Flex gap="2" mb="3">
              <TextField.Root
                placeholder="Search registry"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                style={{ flex: 1 }}
              >
                <TextField.Slot><Search size={14} /></TextField.Slot>
              </TextField.Root>
            </Flex>
            <Flex direction="column" gap="2">
              {registry.length === 0 ? (
                <Text size="2" color="gray">No servers in registry (try a different query).</Text>
              ) : (
                registry.map((entry) => (
                  <Box
                    key={entry.id}
                    style={{ border: "1px solid var(--gray-a5)", borderRadius: 8, padding: 12 }}
                  >
                    <Flex justify="between" align="start">
                      <Box>
                        <Text weight="bold">{entry.name}</Text>
                        <Text size="2" color="gray">{entry.description}</Text>
                        {entry.repository ? (
                          <Text size="1" color="gray">
                            <a href={entry.repository} target="_blank" rel="noreferrer">{entry.repository}</a>
                          </Text>
                        ) : null}
                      </Box>
                      <Button
                        variant="soft"
                        onClick={async () => {
                          await api.post("/api/mcp/servers", {
                            registry_id: entry.id,
                            name: entry.name,
                            transport: "stdio",
                            install_spec: entry.install,
                            config: {},
                            side_effecting: false,
                          });
                          await mutate("/api/mcp/servers");
                        }}
                      >
                        Install
                      </Button>
                    </Flex>
                  </Box>
                ))
              )}
            </Flex>
          </Tabs.Content>
          <Tabs.Content value="installed">
            {activeServerId ? (
              <InstalledServerPanel
                server={installed.find((s) => s.id === activeServerId)!}
                onDelete={async () => {
                  await api.del(`/api/mcp/servers/${activeServerId}`);
                  setActiveServerId(null);
                  await mutate("/api/mcp/servers");
                }}
              />
            ) : (
              <div className="empty-state">Select an installed server from the left</div>
            )}
          </Tabs.Content>
        </Box>
      </Tabs.Root>
    </PageShell>
  );
}

function InstalledServerPanel({ server, onDelete }: { server: McpServer; onDelete: () => void }) {
  const [tools, setTools] = useState<Array<{ name: string; description?: string }>>([]);
  const [error, setError] = useState<string | null>(null);
  const [tool, setTool] = useState("");
  const [args, setArgs] = useState("{}");
  const [result, setResult] = useState<unknown>(null);

  const loadTools = async () => {
    setError(null);
    try {
      const res = await api.get<{ tools: typeof tools; error: string | null }>(
        `/api/mcp/servers/${server.id}/tools`,
      );
      setTools(res.tools);
      if (res.error) setError(res.error);
    } catch (err) {
      setError(String(err));
    }
  };

  const invoke = async () => {
    try {
      const parsed = JSON.parse(args || "{}");
      const res = await api.post(`/api/mcp/servers/${server.id}/invoke`, { tool, arguments: parsed });
      setResult(res);
    } catch (err) {
      setResult({ error: String(err) });
    }
  };

  return (
    <Flex direction="column" gap="3" maxWidth="800px">
      <Flex align="center" justify="between">
        <Box>
          <Text weight="bold" size="4">{server.name}</Text>
          <Text size="2" color="gray">{server.transport} · {server.status}</Text>
        </Box>
        <Flex gap="2">
          <Button variant="soft" onClick={loadTools}>Discover tools</Button>
          <Button color="red" variant="soft" onClick={onDelete}>Uninstall</Button>
        </Flex>
      </Flex>
      {error ? <Text color="red" size="2">{error}</Text> : null}
      {tools.length ? (
        <Box style={{ border: "1px solid var(--gray-a5)", borderRadius: 8, padding: 12 }}>
          <Text weight="bold">Tools</Text>
          <Flex direction="column" gap="1" mt="2">
            {tools.map((t) => (
              <Flex key={t.name} align="center" justify="between">
                <Text size="2">{t.name}</Text>
                <Button size="1" variant="soft" onClick={() => setTool(t.name)}>Use</Button>
              </Flex>
            ))}
          </Flex>
        </Box>
      ) : null}
      <Box style={{ border: "1px solid var(--gray-a5)", borderRadius: 8, padding: 12 }}>
        <Text weight="bold">Invoke</Text>
        <Flex direction="column" gap="2" mt="2">
          <TextField.Root placeholder="tool name" value={tool} onChange={(e) => setTool(e.target.value)} />
          <TextArea rows={5} placeholder='{"arg": "value"}' value={args} onChange={(e) => setArgs(e.target.value)} />
          <Button onClick={invoke}>Invoke</Button>
          {result ? (
            <pre style={{ background: "var(--gray-a2)", padding: 8, borderRadius: 6, fontSize: 12 }}>
              {JSON.stringify(result, null, 2)}
            </pre>
          ) : null}
        </Flex>
      </Box>
    </Flex>
  );
}
