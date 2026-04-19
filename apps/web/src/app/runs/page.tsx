"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Badge, Flex, Text } from "@radix-ui/themes";
import { PageShell, PageHeader } from "@/components/layout/page-shell";
import { SidebarList } from "@/components/common/sidebar-list";
import { useProjects, useRuns } from "@/lib/api/hooks";
import type { Run } from "@/lib/api/types";

const STATUS_COLORS: Record<string, "gray" | "green" | "red" | "amber" | "iris"> = {
  pending: "gray",
  running: "iris",
  succeeded: "green",
  failed: "red",
  cancelled: "amber",
};

export default function RunsListPage() {
  const router = useRouter();
  const { data: projects = [] } = useProjects();
  const [projectId, setProjectId] = useState<string | null>(null);
  const { data: runs = [], isLoading } = useRuns(projectId);

  return (
    <PageShell
      sidebar={
        <Flex direction="column" gap="2">
          <Text size="1" color="gray" weight="bold" style={{ textTransform: "uppercase" }}>Project</Text>
          <SidebarList
            items={[{ id: "", primary: "All projects" }, ...projects.map((p) => ({ id: p.id, primary: p.name }))]}
            activeId={projectId || ""}
            onSelect={(id) => setProjectId(id || null)}
          />
        </Flex>
      }
    >
      <PageHeader title="Runs" subtitle="Each run = one orchestrated execution of a flow against an issue" />
      <Flex direction="column" gap="2">
        {isLoading ? (
          <Text color="gray">Loading...</Text>
        ) : runs.length === 0 ? (
          <div className="empty-state">No runs yet. Pick an issue and start one.</div>
        ) : (
          runs.map((run) => <RunCard key={run.id} run={run} onOpen={() => router.push(`/runs/${run.id}`)} />)
        )}
      </Flex>
    </PageShell>
  );
}

function RunCard({ run, onOpen }: { run: Run; onOpen: () => void }) {
  const color = STATUS_COLORS[run.status] || "gray";
  return (
    <button
      type="button"
      onClick={onOpen}
      style={{
        background: "var(--gray-a2)",
        border: "1px solid var(--gray-a5)",
        borderRadius: 8,
        padding: 12,
        cursor: "pointer",
        textAlign: "left",
      }}
    >
      <Flex justify="between" align="center">
        <Flex direction="column" gap="1">
          <Text weight="bold">{run.title || `Run ${run.id.slice(0, 8)}`}</Text>
          <Text size="1" color="gray">
            {run.dry_run ? "dry-run · " : ""}
            tokens in/out: {run.total_tokens_in}/{run.total_tokens_out} ·
            est. cost ${run.cost_estimate_usd.toFixed(4)}
            {run.issue_number ? ` · issue #${run.issue_number}` : ""}
          </Text>
        </Flex>
        <Flex gap="2" align="center">
          {run.dry_run && <Badge color="amber" variant="soft">dry</Badge>}
          <Badge color={color}>{run.status}</Badge>
        </Flex>
      </Flex>
    </button>
  );
}
