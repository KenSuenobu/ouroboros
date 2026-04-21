"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AlertDialog, Badge, Button, Flex, Text } from "@radix-ui/themes";
import { PageShell, PageHeader } from "@/components/layout/page-shell";
import { SidebarList } from "@/components/common/sidebar-list";
import { useProjects, useRuns } from "@/lib/api/hooks";
import { api } from "@/lib/api/client";
import type { Run } from "@/lib/api/types";
import { mutate } from "swr";

const STATUS_COLORS: Record<string, "gray" | "green" | "red" | "amber" | "iris"> = {
  pending: "gray",
  running: "iris",
  interrupted: "amber",
  succeeded: "green",
  failed: "red",
  cancelled: "amber",
};

export default function RunsListPage() {
  const router = useRouter();
  const { data: projects = [] } = useProjects();
  const [projectId, setProjectId] = useState<string | null>(null);
  const { data: runs = [], isLoading } = useRuns(projectId);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const onDelete = async (runId: string) => {
    setDeleteError(null);
    setDeletingId(runId);
    try {
      await api.del(`/api/runs/${runId}`);
      await mutate((key) => typeof key === "string" && key.startsWith("/api/runs"), undefined, {
        revalidate: true,
      });
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Failed to delete run.");
    } finally {
      setDeletingId(null);
    }
  };

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
        {deleteError ? <Text color="red">{deleteError}</Text> : null}
        {isLoading ? (
          <Text color="gray">Loading...</Text>
        ) : runs.length === 0 ? (
          <div className="empty-state">No runs yet. Pick an issue and start one.</div>
        ) : (
          runs.map((run) => (
            <RunCard
              key={run.id}
              run={run}
              deleting={deletingId === run.id}
              onOpen={() => router.push(`/runs/${run.id}`)}
              onDelete={() => onDelete(run.id)}
            />
          ))
        )}
      </Flex>
    </PageShell>
  );
}

function RunCard({
  run,
  deleting,
  onOpen,
  onDelete,
}: {
  run: Run;
  deleting: boolean;
  onOpen: () => void;
  onDelete: () => Promise<void>;
}) {
  const color = STATUS_COLORS[run.status] || "gray";
  return (
    <Flex
      style={{
        background: "var(--gray-a2)",
        border: "1px solid var(--gray-a5)",
        borderRadius: 8,
        padding: 12,
      }}
      justify="between"
      align="center"
      gap="3"
    >
      <button
        type="button"
        onClick={onOpen}
        style={{
          textAlign: "left",
          background: "transparent",
          border: "none",
          cursor: "pointer",
          width: "100%",
          padding: 0,
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
      <AlertDialog.Root>
        <AlertDialog.Trigger>
          <Button
            type="button"
            variant="soft"
            color="red"
            size="1"
            disabled={deleting}
          >
            {deleting ? "Deleting..." : "Delete"}
          </Button>
        </AlertDialog.Trigger>
        <AlertDialog.Content maxWidth="460px">
          <AlertDialog.Title>Delete run history?</AlertDialog.Title>
          <AlertDialog.Description>
            This removes the run and its recorded steps/artifacts permanently.
          </AlertDialog.Description>
          <Flex justify="end" mt="4" gap="2">
            <AlertDialog.Cancel>
              <Button variant="soft" color="gray">Cancel</Button>
            </AlertDialog.Cancel>
            <AlertDialog.Action>
              <Button color="red" onClick={onDelete} disabled={deleting}>
                Delete run
              </Button>
            </AlertDialog.Action>
          </Flex>
        </AlertDialog.Content>
      </AlertDialog.Root>
    </Flex>
  );
}
