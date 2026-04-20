"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AlertDialog,
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
import { useProjectIntrospection, useProjects } from "@/lib/api/hooks";
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
  access_token: "",
};

export default function ProjectsPage() {
  const { data: projects = [], isLoading } = useProjects();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [draft, setDraft] = useState<ProjectInput | null>(null);
  const [repoTestState, setRepoTestState] = useState<{ status: "idle" | "testing" | "ok" | "error"; message?: string }>({ status: "idle" });
  const [repoTestAlert, setRepoTestAlert] = useState<{
    open: boolean;
    title: string;
    message: string;
  }>({ open: false, title: "", message: "" });
  const [oauth, setOauth] = useState<{
    deviceCode: string;
    userCode: string;
    verificationUri: string;
    interval: number;
  } | null>(null);
  const [oauthPending, setOauthPending] = useState(false);
  const [oauthError, setOauthError] = useState<string | null>(null);
  const { data: introspection } = useProjectIntrospection(activeId);

  const active = activeId ? projects.find((p) => p.id === activeId) ?? null : null;
  const editing = draft ?? (active ? projectToInput(active) : null);

  const startNew = () => {
    setActiveId(null);
    setDraft({ ...EMPTY });
  };

  const update = (patch: Partial<ProjectInput>) => setDraft({ ...(editing as ProjectInput), ...patch });
  const isGithubRepo = useMemo(
    () => Boolean(editing?.repo_url?.trim().toLowerCase().startsWith("https://github.com/")),
    [editing?.repo_url],
  );

  useEffect(() => {
    setOauth(null);
    setOauthError(null);
    setOauthPending(false);
  }, [editing?.repo_url]);

  useEffect(() => {
    setRepoTestState({ status: "idle" });
  }, [editing?.repo_url, editing?.default_branch, editing?.access_token]);

  const onSave = async () => {
    if (!editing) return;
    const payload: ProjectInput = { ...editing };
    if (!payload.access_token?.trim()) {
      delete payload.access_token;
    } else {
      payload.access_token = payload.access_token.trim();
    }
    if (active) {
      await api.put<Project>(`/api/projects/${active.id}`, payload);
    } else {
      const created = await api.post<Project>("/api/projects", payload);
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

  const testRepositoryAccess = async () => {
    if (!editing?.repo_url.trim()) {
      setRepoTestState({ status: "error", message: "Enter a repository URL first." });
      return;
    }
    setRepoTestState({ status: "testing" });
    try {
      const result = await api.post<{ ok: boolean; message: string }>(`/api/projects/test-repo`, {
        repo_url: editing.repo_url.trim(),
        default_branch: editing.default_branch || "main",
        access_token: editing.access_token?.trim() || undefined,
      });
      setRepoTestState({ status: result.ok ? "ok" : "error", message: result.message });
      setRepoTestAlert({
        open: true,
        title: result.ok ? "Repository verified" : "Repository verification failed",
        message: result.message,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Repository test failed.";
      setRepoTestState({ status: "error", message });
      setRepoTestAlert({
        open: true,
        title: "Repository verification failed",
        message,
      });
    }
  };

  const startGitHubOAuth = async () => {
    if (!editing) return;
    setOauthError(null);
    setOauthPending(true);
    try {
      const started = await api.post<{
        device_code: string;
        user_code: string;
        verification_uri: string;
        expires_in: number;
        interval: number;
      }>("/api/projects/oauth/github/device/start", { repo_url: editing.repo_url });
      setOauth({
        deviceCode: started.device_code,
        userCode: started.user_code,
        verificationUri: started.verification_uri,
        interval: started.interval || 5,
      });
    } catch (err) {
      setOauthError(err instanceof Error ? err.message : "Failed to start GitHub OAuth.");
    } finally {
      setOauthPending(false);
    }
  };

  const fetchGitHubToken = async () => {
    if (!oauth) return;
    setOauthError(null);
    setOauthPending(true);
    try {
      const polled = await api.post<{
        status: string;
        access_token?: string;
        error?: string;
        error_description?: string;
      }>("/api/projects/oauth/github/device/poll", { device_code: oauth.deviceCode });

      if (polled.status === "authorized" && polled.access_token) {
        update({ access_token: polled.access_token });
        setOauth(null);
        return;
      }
      if (polled.status === "pending") {
        setOauthError("Authorization pending. Complete the GitHub step, then click fetch again.");
        return;
      }
      setOauthError(polled.error_description || polled.error || "GitHub OAuth failed.");
    } catch (err) {
      setOauthError(err instanceof Error ? err.message : "Failed to fetch GitHub token.");
    } finally {
      setOauthPending(false);
    }
  };

  return (
    <>
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
              <Flex gap="2" align="center">
                <TextField.Root
                  style={{ flex: 1 }}
                  value={editing.repo_url}
                  onChange={(e) => update({ repo_url: e.target.value })}
                />
                <Button
                  variant="soft"
                  color={repoTestState.status === "ok" ? "green" : repoTestState.status === "error" ? "red" : "gray"}
                  disabled={repoTestState.status === "testing" || !editing.repo_url.trim()}
                  onClick={testRepositoryAccess}
                >
                  {repoTestState.status === "testing" ? "Testing..." : "Test repo"}
                </Button>
              </Flex>
            </Field>
            <Field label="Repository access token (optional)">
              <TextField.Root
                type="password"
                placeholder={active?.has_access_token ? "Leave blank to keep existing token" : "Paste token for private repo access"}
                value={editing.access_token || ""}
                onChange={(e) => update({ access_token: e.target.value })}
              />
              {active?.has_access_token ? (
                <Text mt="1" size="1" color="gray">A token is already stored; enter a new one to replace it.</Text>
              ) : null}
              {isGithubRepo ? (
                <Flex mt="2" direction="column" gap="2">
                  <Button size="1" variant="soft" onClick={startGitHubOAuth} disabled={oauthPending}>
                    {oauth ? "Restart GitHub OAuth" : "Create token with GitHub OAuth"}
                  </Button>
                  {oauth ? (
                    <Box style={{ border: "1px solid var(--gray-a5)", borderRadius: 8, padding: 8 }}>
                      <Text size="1">Open <a href={oauth.verificationUri} target="_blank" rel="noreferrer">{oauth.verificationUri}</a> and enter code <strong>{oauth.userCode}</strong>.</Text>
                      <Flex mt="2" gap="2" align="center">
                        <Button size="1" onClick={fetchGitHubToken} disabled={oauthPending}>Fetch token</Button>
                        <Text size="1" color="gray">Poll every ~{oauth.interval}s</Text>
                      </Flex>
                    </Box>
                  ) : null}
                </Flex>
              ) : null}
              {oauthError ? <Text mt="1" size="1" color="red">{oauthError}</Text> : null}
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
                {active ? (
                  <SuggestionChips
                    commands={introspection?.build ?? []}
                    current={editing.build_command}
                    onUse={(command) => update({ build_command: command })}
                  />
                ) : null}
              </Field>
              <Field label="Test command" style={{ flex: 1 }}>
                <TextField.Root
                  placeholder="npm test"
                  value={editing.test_command || ""}
                  onChange={(e) => update({ test_command: e.target.value || null })}
                />
                {active ? (
                  <SuggestionChips
                    commands={introspection?.test ?? []}
                    current={editing.test_command}
                    onUse={(command) => update({ test_command: command })}
                  />
                ) : null}
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
      <AlertDialog.Root open={repoTestAlert.open} onOpenChange={(open) => setRepoTestAlert((prev) => ({ ...prev, open }))}>
        <AlertDialog.Content maxWidth="460px">
          <AlertDialog.Title>{repoTestAlert.title}</AlertDialog.Title>
          <AlertDialog.Description>{repoTestAlert.message}</AlertDialog.Description>
          <Flex justify="end" mt="4">
            <AlertDialog.Action>
              <Button onClick={() => setRepoTestAlert({ open: false, title: "", message: "" })}>OK</Button>
            </AlertDialog.Action>
          </Flex>
        </AlertDialog.Content>
      </AlertDialog.Root>
    </>
  );
}

function projectToInput(project: Project): ProjectInput {
  return {
    name: project.name,
    repo_url: project.repo_url,
    scm_kind: project.scm_kind,
    default_branch: project.default_branch,
    local_clone_hint: project.local_clone_hint,
    default_flow_id: project.default_flow_id,
    build_command: project.build_command,
    test_command: project.test_command,
    config: project.config,
    access_token: "",
  };
}

function SuggestionChips({
  commands,
  current,
  onUse,
}: {
  commands: string[];
  current: string | null;
  onUse: (command: string) => void;
}) {
  const options = commands.filter((command) => command !== current);
  if (!options.length) return null;
  return (
    <Flex mt="2" gap="2" wrap="wrap" align="center">
      <Text size="1" color="gray">
        Suggestions
      </Text>
      {options.map((command) => (
        <Button key={command} size="1" variant="soft" onClick={() => onUse(command)}>
          Use this: {command}
        </Button>
      ))}
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
