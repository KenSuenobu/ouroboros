"use client";

import { use, useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { Badge, Box, Button, Dialog, Flex, Tabs, Text, TextField } from "@radix-ui/themes";
import { PageShell, PageHeader } from "@/components/layout/page-shell";
import { LogPane } from "@/components/runs/log-pane";
import { useRun } from "@/lib/api/hooks";
import { api } from "@/lib/api/client";
import { useRunStream } from "@/lib/ws/use-run-stream";
import type { Intervention, Run, RunEvent, RunStep } from "@/lib/api/types";
import { mutate } from "swr";

const PlanFlow = dynamic(() => import("@/components/flow/run-plan-flow").then((m) => m.RunPlanFlow), { ssr: false });
const MonacoDiff = dynamic(() => import("@/components/editors/diff-viewer").then((m) => m.DiffViewer), { ssr: false });

const STATUS_COLOR: Record<string, "gray" | "iris" | "green" | "red" | "amber"> = {
  pending: "gray",
  running: "iris",
  interrupted: "amber",
  succeeded: "green",
  failed: "red",
  cancelled: "amber",
};

export default function RunDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: run } = useRun(id);
  const { events } = useRunStream(id);
  const [intervention, setIntervention] = useState<Intervention | null>(null);
  const [answer, setAnswer] = useState("");

  useEffect(() => {
    let alive = true;
    const fetchInterventions = async () => {
      try {
        const list = await api.get<Intervention[]>(`/api/runs/${id}/interventions`);
        if (!alive) return;
        const pending = list.find((i) => i.status === "pending");
        setIntervention(pending || null);
      } catch {
        /* ignore */
      }
    };
    fetchInterventions();
    const t = setInterval(fetchInterventions, 2000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [id, events.length]);

  const eventsByStepId = useMemo(() => {
    const map = new Map<string, RunEvent[]>();
    for (const evt of events) {
      const stepId = (evt.payload?.step_id as string) || "";
      if (stepId) {
        const arr = map.get(stepId);
        if (arr) {
          arr.push(evt);
        } else {
          map.set(stepId, [evt]);
        }
      }
    }
    return map;
  }, [events]);

  const cancel = async () => {
    await api.post(`/api/runs/${id}/cancel`);
    await mutate(`/api/runs/${id}`);
  };

  const retry = async (dryRun?: boolean) => {
    const fresh = await api.post<Run>(`/api/runs/${id}/retry${dryRun !== undefined ? `?dry_run=${dryRun}` : ""}`);
    window.location.href = `/runs/${fresh.id}`;
  };

  const resume = async () => {
    await api.post<Run>(`/api/runs/${id}/resume`);
    await mutate(`/api/runs/${id}`);
    await mutate("/api/runs");
  };

  const submitIntervention = async () => {
    if (!intervention) return;
    await api.post(`/api/runs/${id}/interventions/${intervention.id}`, { answer: { text: answer } });
    setIntervention(null);
    setAnswer("");
  };

  return (
    <PageShell
      sidebar={
        <Flex direction="column" gap="3">
          <Text size="1" color="gray" weight="bold" style={{ textTransform: "uppercase" }}>Steps</Text>
          {run?.steps?.length ? (
            run.steps.map((step) => <StepRow key={step.id} step={step} active={false} />)
          ) : (
            <Text size="2" color="gray">No steps yet</Text>
          )}
        </Flex>
      }
    >
      <PageHeader
        title={run?.title || `Run ${id.slice(0, 8)}`}
        subtitle={
          run
            ? `${run.dry_run ? "dry-run · " : ""}status: ${run.status} · tokens ${run.total_tokens_in}/${run.total_tokens_out} · est $${run.cost_estimate_usd.toFixed(4)}`
            : "loading..."
        }
        actions={
          run ? (
            <Flex gap="2">
              {run.status === "running" ? (
                <Button color="amber" variant="soft" onClick={cancel}>Cancel</Button>
              ) : null}
              {run.status === "interrupted" ? (
                <Button color="amber" onClick={resume}>Resume</Button>
              ) : null}
              <Button
                variant="soft"
                onClick={() => window.open(`/api/runs/${id}/summary.md`, "_blank")}
              >
                Export summary.md
              </Button>
              {run.dry_run && ["succeeded", "failed", "cancelled"].includes(run.status) ? (
                <Button
                  color="green"
                  onClick={async () => {
                    const fresh = await api.post<Run>(`/api/runs/${id}/promote`);
                    window.location.href = `/runs/${fresh.id}`;
                  }}
                >
                  Promote to real run
                </Button>
              ) : null}
              <Button variant="soft" onClick={() => retry(true)}>Retry as dry-run</Button>
              <Button onClick={() => retry(false)}>Retry as real run</Button>
            </Flex>
          ) : null
        }
      />

      <Tabs.Root defaultValue="plan">
        <Tabs.List>
          <Tabs.Trigger value="plan">Plan</Tabs.Trigger>
          <Tabs.Trigger value="timeline">Timeline</Tabs.Trigger>
          <Tabs.Trigger value="events">Events</Tabs.Trigger>
        </Tabs.List>
        <Box mt="3">
          <Tabs.Content value="plan">
            <div className="flow-wrapper">
              <PlanFlow
                graph={run?.plan || { nodes: [], edges: [] }}
                stepStatuses={Object.fromEntries((run?.steps || []).map((s) => [s.node_id, s.status]))}
              />
            </div>
          </Tabs.Content>
          <Tabs.Content value="timeline">
            <Flex direction="column" gap="3">
              {(run?.steps || []).map((step) => (
                <StepDetail key={step.id} runId={id} step={step} events={eventsByStepId.get(step.id) || []} />
              ))}
            </Flex>
          </Tabs.Content>
          <Tabs.Content value="events">
            <Box style={{ background: "var(--gray-a2)", padding: 12, borderRadius: 6, fontFamily: "monospace", fontSize: 12 }}>
              {events.length === 0 ? <Text color="gray">No events yet</Text> : null}
              {events.map((evt, i) => (
                <div key={i} style={{ borderBottom: "1px dashed var(--gray-a5)", padding: "4px 0" }}>
                  <strong>{evt.type}</strong> · {evt.timestamp}
                  <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{JSON.stringify(evt.payload, null, 2)}</pre>
                </div>
              ))}
            </Box>
          </Tabs.Content>
        </Box>
      </Tabs.Root>

      <Dialog.Root open={!!intervention} onOpenChange={(open) => !open && setIntervention(null)}>
        <Dialog.Content style={{ maxWidth: 480 }}>
          <Dialog.Title>Run paused for input</Dialog.Title>
          <Dialog.Description>{intervention?.prompt}</Dialog.Description>
          {(intervention?.options || []).length ? (
            <Flex direction="column" gap="2" mt="3">
              {intervention?.options.map((opt) => (
                <Button
                  key={opt.id}
                  variant="soft"
                  onClick={async () => {
                    await api.post(`/api/runs/${id}/interventions/${intervention!.id}`, { answer: { id: opt.id } });
                    setIntervention(null);
                  }}
                >
                  {opt.label}
                </Button>
              ))}
            </Flex>
          ) : (
            <Flex direction="column" gap="2" mt="3">
              <TextField.Root value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder="Type your answer" />
              <Flex gap="2" justify="end">
                <Dialog.Close><Button variant="soft" color="gray">Cancel</Button></Dialog.Close>
                <Button onClick={submitIntervention}>Submit</Button>
              </Flex>
            </Flex>
          )}
        </Dialog.Content>
      </Dialog.Root>

      <_MonacoPreload />
    </PageShell>
  );
}

function _MonacoPreload() {
  return <MonacoDiff original="" modified="" hidden />;
}

function StepRow({ step }: { step: RunStep; active: boolean }) {
  return (
    <Flex
      direction="column"
      gap="1"
      style={{
        border: "1px solid var(--gray-a5)",
        borderRadius: 6,
        padding: 8,
      }}
    >
      <Flex align="center" justify="between">
        <Text size="2" weight="bold">{step.node_id}</Text>
        <Badge color={STATUS_COLOR[step.status] || "gray"}>{step.status}</Badge>
      </Flex>
      <Text size="1" color="gray">
        {step.dry_run ? "dry · " : ""}
        attempt {step.attempt}{step.model_used ? ` · ${step.model_used}` : ""}
      </Text>
      {step.summary ? (
        <Text size="1" color="gray" style={{ maxHeight: 60, overflow: "hidden" }}>
          {step.summary}
        </Text>
      ) : null}
    </Flex>
  );
}

function StepDetail({ runId, step, events }: { runId: string; step: RunStep; events: RunEvent[] }) {
  const [artifacts, setArtifacts] = useState<Array<{ id: string; kind: string; name: string; inline_content: string | null }>>([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    api.get<typeof artifacts>(`/api/runs/${runId}/steps/${step.id}/artifacts`).then(setArtifacts).catch(() => setArtifacts([]));
  }, [open, runId, step.id]);

  return (
    <Box style={{ border: "1px solid var(--gray-a5)", borderRadius: 8, padding: 12 }}>
      <Flex align="center" justify="between">
        <Flex direction="column" gap="1">
          <Text weight="bold">{step.node_id}</Text>
          <Text size="1" color="gray">
            {step.summary || "(no summary)"} {step.error ? ` · error: ${step.error}` : ""}
          </Text>
        </Flex>
        <Flex gap="2" align="center">
          <Badge color={STATUS_COLOR[step.status] || "gray"}>{step.status}</Badge>
          <Button size="1" variant="soft" onClick={() => setOpen((v) => !v)}>
            {open ? "Hide artifacts" : "Show artifacts"}
          </Button>
        </Flex>
      </Flex>
      <Box mt="2">
        <LogPane stepId={step.id} events={events} isRunning={step.status === "running"} />
      </Box>
      {open && (
        <Flex direction="column" gap="2" mt="2">
          {artifacts.length === 0 ? (
            <Text size="2" color="gray">No artifacts</Text>
          ) : (
            artifacts.map((a) => (
              <Box key={a.id} style={{ background: "var(--gray-a2)", padding: 8, borderRadius: 6 }}>
                <Flex align="center" justify="between">
                  <Text size="2" weight="bold">{a.name}</Text>
                  <Badge variant="soft">{a.kind}</Badge>
                </Flex>
                {a.kind === "file_diff" ? (
                  <Box style={{ height: 200, marginTop: 6 }}>
                    <MonacoDiff original="" modified={a.inline_content || ""} language="diff" />
                  </Box>
                ) : (
                  <pre style={{ margin: 0, fontSize: 12, maxHeight: 220, overflow: "auto", whiteSpace: "pre-wrap" }}>
                    {a.inline_content || ""}
                  </pre>
                )}
              </Box>
            ))
          )}
        </Flex>
      )}
    </Box>
  );
}
