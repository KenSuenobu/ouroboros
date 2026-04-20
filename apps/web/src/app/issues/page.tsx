"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Badge, Box, Button, Flex, Select, Text, TextField } from "@radix-ui/themes";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Search } from "lucide-react";
import { PageShell, PageHeader } from "@/components/layout/page-shell";
import { SidebarList } from "@/components/common/sidebar-list";
import { useIssues, useProjects, useRoadmap } from "@/lib/api/hooks";
import { api } from "@/lib/api/client";
import type { Issue, Run } from "@/lib/api/types";
import { mutate } from "swr";

export default function IssuesPage() {
  const { data: projects = [] } = useProjects();
  const [projectId, setProjectId] = useState<string | null>(null);
  const router = useRouter();

  const effectiveProject = projectId || projects[0]?.id || null;
  const [stateFilter, setStateFilter] = useState<"open" | "closed">("open");
  const [search, setSearch] = useState("");
  const [labelFilter, setLabelFilter] = useState<string>("");
  const [groupBy, setGroupBy] = useState<"none" | "label" | "milestone">("none");
  const [sortBy, setSortBy] = useState<"number" | "title">("number");
  const [activeId, setActiveId] = useState<string | null>(null);
  const [dryRun, setDryRun] = useState(true);

  const { data: issues = [], isLoading } = useIssues(effectiveProject, stateFilter);
  const { data: roadmap = [] } = useRoadmap(effectiveProject);

  const filtered = useMemo(() => {
    let list = issues;
    if (search) {
      const q = search.toLowerCase();
      list = list.filter((i) => i.title.toLowerCase().includes(q) || (i.body || "").toLowerCase().includes(q));
    }
    if (labelFilter) list = list.filter((i) => i.labels.includes(labelFilter));
    list = [...list].sort((a, b) => (sortBy === "number" ? b.number - a.number : a.title.localeCompare(b.title)));
    return list;
  }, [issues, search, labelFilter, sortBy]);

  const grouped = useMemo(() => {
    if (groupBy === "none") return [{ key: "All issues", items: filtered }];
    const map = new Map<string, Issue[]>();
    for (const issue of filtered) {
      const keys = groupBy === "label" ? issue.labels.length ? issue.labels : ["(no label)"] : [issue.milestone || "(no milestone)"];
      for (const key of keys) {
        const arr = map.get(key) || [];
        arr.push(issue);
        map.set(key, arr);
      }
    }
    return Array.from(map.entries()).map(([key, items]) => ({ key, items }));
  }, [filtered, groupBy]);

  const allLabels = useMemo(() => {
    const set = new Set<string>();
    issues.forEach((i) => i.labels.forEach((l) => set.add(l)));
    return Array.from(set).sort();
  }, [issues]);

  const active = activeId ? issues.find((i) => i.id === activeId) ?? null : null;
  const matchedRoadmap = useMemo(() => {
    if (!active) return [];
    const haystack = `${active.title} ${active.body || ""}`.toLowerCase();
    return roadmap
      .map((entry) => {
        const tokens = entry.title.toLowerCase().split(/\W+/).filter((t) => t.length > 4);
        const score = tokens.reduce((acc, t) => (haystack.includes(t) ? acc + 1 : acc), 0);
        return { entry, score };
      })
      .filter((m) => m.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 6);
  }, [active, roadmap]);

  const sync = async () => {
    if (!effectiveProject) return;
    await api.post(`/api/projects/${effectiveProject}/issues/sync?state=${stateFilter}`);
    await mutate(`/api/projects/${effectiveProject}/issues?state=${stateFilter}`);
  };

  const syncRoadmap = async () => {
    if (!effectiveProject) return;
    await api.post(`/api/projects/${effectiveProject}/roadmap/sync`);
    await mutate(`/api/projects/${effectiveProject}/roadmap`);
  };

  const startRun = async () => {
    if (!active || !effectiveProject) return;
    const run = await api.post<Run>("/api/runs", {
      project_id: effectiveProject,
      issue_id: active.id,
      issue_number: active.number,
      dry_run: dryRun,
      title: active.title,
    });
    router.push(`/runs/${run.id}`);
  };

  return (
    <PageShell
      sidebar={
        <Flex direction="column" gap="3">
          <Field label="Project">
            <Select.Root value={effectiveProject || ""} onValueChange={setProjectId}>
              <Select.Trigger />
              <Select.Content>
                {projects.map((p) => (
                  <Select.Item key={p.id} value={p.id}>{p.name}</Select.Item>
                ))}
              </Select.Content>
            </Select.Root>
          </Field>
          <Field label="State">
            <Select.Root value={stateFilter} onValueChange={(v) => setStateFilter(v as "open" | "closed")}>
              <Select.Trigger />
              <Select.Content>
                <Select.Item value="open">Open</Select.Item>
                <Select.Item value="closed">Closed</Select.Item>
              </Select.Content>
            </Select.Root>
          </Field>
          <Field label="Label">
            <Select.Root value={labelFilter || "__all__"} onValueChange={(v) => setLabelFilter(v === "__all__" ? "" : v)}>
              <Select.Trigger />
              <Select.Content>
                <Select.Item value="__all__">(all)</Select.Item>
                {allLabels.map((l) => (
                  <Select.Item key={l} value={l}>{l}</Select.Item>
                ))}
              </Select.Content>
            </Select.Root>
          </Field>
          <Field label="Group by">
            <Select.Root value={groupBy} onValueChange={(v) => setGroupBy(v as "none" | "label" | "milestone")}>
              <Select.Trigger />
              <Select.Content>
                <Select.Item value="none">None</Select.Item>
                <Select.Item value="label">Label</Select.Item>
                <Select.Item value="milestone">Milestone</Select.Item>
              </Select.Content>
            </Select.Root>
          </Field>
          <Field label="Sort">
            <Select.Root value={sortBy} onValueChange={(v) => setSortBy(v as "number" | "title")}>
              <Select.Trigger />
              <Select.Content>
                <Select.Item value="number">Number</Select.Item>
                <Select.Item value="title">Title</Select.Item>
              </Select.Content>
            </Select.Root>
          </Field>
          <TextField.Root placeholder="Search title/body" value={search} onChange={(e) => setSearch(e.target.value)}>
            <TextField.Slot><Search size={14} /></TextField.Slot>
          </TextField.Root>
          <Flex gap="2">
            <Button variant="soft" onClick={sync} disabled={!effectiveProject}>Sync issues</Button>
            <Button variant="soft" onClick={syncRoadmap} disabled={!effectiveProject}>Sync roadmap</Button>
          </Flex>
          <Box style={{ borderTop: "1px solid var(--gray-a5)", paddingTop: 12 }}>
            {grouped.map((group) => (
              <Flex direction="column" gap="1" key={group.key} mb="3">
                {groupBy !== "none" && (
                  <Text size="1" color="gray" weight="bold" style={{ textTransform: "uppercase" }}>
                    {group.key} ({group.items.length})
                  </Text>
                )}
                <SidebarList
                  items={group.items.map((i) => ({
                    id: i.id,
                    primary: `#${i.number} ${i.title}`,
                    secondary: i.labels.slice(0, 3).join(", ") || undefined,
                    badge: i.state === "open" ? <Badge color="green">open</Badge> : <Badge color="gray">closed</Badge>,
                  }))}
                  activeId={activeId}
                  onSelect={setActiveId}
                  emptyLabel={isLoading ? "Loading..." : "No issues"}
                />
              </Flex>
            ))}
          </Box>
        </Flex>
      }
    >
      <PageHeader
        title={active ? `#${active.number} - ${active.title}` : "Issues"}
        subtitle={active ? `state: ${active.state}` : "Browse, sort, group, and pair to roadmap entries"}
        actions={
          active ? (
            <Flex gap="2" align="center">
              <Flex align="center" gap="2">
                <Text size="2" color="gray">Dry run</Text>
                <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
              </Flex>
              <Button onClick={startRun}>Run this issue</Button>
            </Flex>
          ) : null
        }
      />
      {active ? (
        <Flex direction="column" gap="4">
          <Flex gap="2" wrap="wrap">
            {active.labels.map((l) => (
              <Badge key={l} color="iris" variant="soft">{l}</Badge>
            ))}
            {active.url ? (
              <a href={active.url} target="_blank" rel="noreferrer">
                <Badge color="gray" variant="soft">Open in SCM</Badge>
              </a>
            ) : null}
          </Flex>
          <Box
            className="issue-markdown"
            style={{
              border: "1px solid var(--gray-a5)",
              borderRadius: 8,
              padding: 16,
              background: "var(--gray-a2)",
            }}
          >
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{active.body || "(no body)"}</ReactMarkdown>
          </Box>
          <Box>
            <Text size="3" weight="bold">Roadmap pairings</Text>
            <Flex direction="column" gap="2" mt="2">
              {matchedRoadmap.length === 0 ? (
                <Text size="2" color="gray">No roadmap matches detected. Sync roadmap to populate.</Text>
              ) : (
                matchedRoadmap.map(({ entry, score }) => (
                  <Box
                    key={entry.id}
                    style={{
                      border: "1px solid var(--gray-a5)",
                      borderRadius: 6,
                      padding: 10,
                    }}
                  >
                    <Flex align="center" justify="between">
                      <Text weight="bold">{entry.title}</Text>
                      <Badge color="gray" variant="soft">match: {score}</Badge>
                    </Flex>
                    <Text size="1" color="gray">
                      {entry.kind} - {entry.file_path}
                    </Text>
                  </Box>
                ))
              )}
            </Flex>
          </Box>
        </Flex>
      ) : (
        <div className="empty-state">Select an issue from the left</div>
      )}
    </PageShell>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <Flex direction="column" gap="1">
      <Text size="1" color="gray" weight="bold" style={{ textTransform: "uppercase" }}>{label}</Text>
      {children}
    </Flex>
  );
}
