"use client";

import { useState } from "react";
import {
  Box,
  Button,
  Flex,
  Select,
  Text,
  TextField,
  TextArea,
} from "@radix-ui/themes";
import { PageShell, PageHeader } from "@/components/layout/page-shell";
import { SidebarList } from "@/components/common/sidebar-list";
import { useProjects } from "@/lib/api/hooks";
import { api } from "@/lib/api/client";
import type { Project, ProjectInput } from "@/lib/api/types";
import { mutate } from "swr";

const EMPTY: ProjectInput = {
  name: "",
  repo_url: "",
  scm_kind: "github",
  default_branch: "main",
  local_clone_hint: null,
  default_flow_id: null,
  build_command: null,
  test_command: null,
  config: {},
};

export default function ProjectsPage() {
  const { data: projects = [], isLoading } = useProjects();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [draft, setDraft] = useState<ProjectInput | null>(null);

  const active = activeId ? projects.find((p) => p.id === activeId) ?? null : null;
  const editing = draft ?? (active as ProjectInput | null);

  const startNew = () => {
    setActiveId(null);
    setDraft({ ...EMPTY });
  };

  const update = (patch: Partial<ProjectInput>) => setDraft({ ...(editing as ProjectInput), ...patch });

  const onSave = async () => {
    if (!editing) return;
    if (active) {
      await api.put<Project>(`/api/projects/${active.id}`, editing);
    } else {
      const created = await api.post<Project>("/api/projects", editing);
      setActiveId(created.id);
    }
    setDraft(null);
    await mutate("/api/projects");
  };

  const onDelete = async () => {
    if (!active) return;
    await api.del(`/api/projects/${active.id}`);
    setActiveId(null);
    await mutate("/api/projects");
  };

  return (
    <PageShell
      sidebar={
        <SidebarList
          title="Projects"
          items={projects.map((p) => ({ id: p.id, primary: p.name, secondary: p.repo_url }))}
          activeId={activeId}
          onSelect={(id) => {
            setActiveId(id);
            setDraft(null);
          }}
          onAdd={startNew}
          emptyLabel={isLoading ? "Loading..." : "No projects yet"}
        />
      }
    >
      <PageHeader
        title={active ? active.name : draft ? "New project" : "Projects"}
        subtitle={active ? active.repo_url : draft ? "Configure the repo to orchestrate" : "Pick a project on the left or add a new one"}
        actions={
          editing ? (
            <Flex gap="2">
              {active ? (
                <Button color="red" variant="soft" onClick={onDelete}>Delete</Button>
              ) : null}
              <Button onClick={onSave}>{active ? "Save" : "Create"}</Button>
            </Flex>
          ) : null
        }
      />
      {editing ? (
        <Box maxWidth="720px">
          <Flex direction="column" gap="3">
            <Field label="Name">
              <TextField.Root value={editing.name} onChange={(e) => update({ name: e.target.value })} />
            </Field>
            <Field label="Repository URL">
              <TextField.Root value={editing.repo_url} onChange={(e) => update({ repo_url: e.target.value })} />
            </Field>
            <Flex gap="3">
              <Field label="SCM" style={{ flex: 1 }}>
                <Select.Root value={editing.scm_kind} onValueChange={(v) => update({ scm_kind: v as "github" | "gitlab" })}>
                  <Select.Trigger />
                  <Select.Content>
                    <Select.Item value="github">GitHub</Select.Item>
                    <Select.Item value="gitlab">GitLab</Select.Item>
                  </Select.Content>
                </Select.Root>
              </Field>
              <Field label="Default branch" style={{ flex: 1 }}>
                <TextField.Root value={editing.default_branch} onChange={(e) => update({ default_branch: e.target.value })} />
              </Field>
            </Flex>
            <Field label="Local clone hint (optional, used for roadmap parsing)">
              <TextField.Root
                value={editing.local_clone_hint || ""}
                onChange={(e) => update({ local_clone_hint: e.target.value || null })}
              />
            </Field>
            <Flex gap="3">
              <Field label="Build command" style={{ flex: 1 }}>
                <TextField.Root
                  placeholder="npm run build"
                  value={editing.build_command || ""}
                  onChange={(e) => update({ build_command: e.target.value || null })}
                />
              </Field>
              <Field label="Test command" style={{ flex: 1 }}>
                <TextField.Root
                  placeholder="npm test"
                  value={editing.test_command || ""}
                  onChange={(e) => update({ test_command: e.target.value || null })}
                />
              </Field>
            </Flex>
            <Field label="Config (JSON, advanced)">
              <TextArea
                value={JSON.stringify(editing.config || {}, null, 2)}
                onChange={(e) => {
                  try {
                    update({ config: JSON.parse(e.target.value || "{}") });
                  } catch {
                    /* ignore */
                  }
                }}
                rows={5}
              />
            </Field>
          </Flex>
        </Box>
      ) : (
        <div className="empty-state">Select or create a project</div>
      )}
    </PageShell>
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
