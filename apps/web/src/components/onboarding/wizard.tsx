"use client";

import { useState, useEffect, useRef } from "react";
import type { ReactNode } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Button, Flex, Select, Text, TextField } from "@radix-ui/themes";
import { mutate } from "swr";
import { useWorkspaceOnboarding } from "@/lib/api/hooks";
import { api } from "@/lib/api/client";
import type { ProjectInput, ProviderInput, Provider } from "@/lib/api/types";

type Step = 1 | 2 | 3;

const EMPTY_PROJECT: ProjectInput = {
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

const DEFAULT_PROVIDER_URL: Record<Provider["kind"], string | null> = {
  ollama: "http://localhost:11434",
  anthropic: "https://api.anthropic.com",
  github_models: "https://models.github.ai",
  opencode: null,
  gh_copilot: null,
};

export function OnboardingWizard() {
  const { data, isLoading } = useWorkspaceOnboarding();
  const [step, setStep] = useState<Step>(1);
  const [dismissed, setDismissed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [workspaceName, setWorkspaceName] = useState("");
  const [project, setProject] = useState<ProjectInput>(EMPTY_PROJECT);
  const [provider, setProvider] = useState<ProviderInput>({
    name: "Local Ollama",
    kind: "ollama",
    base_url: DEFAULT_PROVIDER_URL.ollama,
    config: {},
    enabled: true,
  });

  const nameInitialized = useRef(false);

  useEffect(() => {
    if (data?.name && !nameInitialized.current) {
      nameInitialized.current = true;
      setWorkspaceName(data.name);
    }
  }, [data?.name]);

  if (!data && !isLoading) {
    return null;
  }

  const shouldShow = Boolean(data?.requires_onboarding) && !dismissed;

  const canAdvanceStepOne = workspaceName.trim().length > 0;
  const canAdvanceStepTwo = project.name.trim().length > 0 && project.repo_url.trim().length > 0;
  const canAdvanceStepThree =
    provider.name.trim().length > 0 &&
    (provider.kind !== "anthropic" || Boolean(provider.api_key?.trim()));

  const stepTitle =
    step === 1 ? "Name your workspace" : step === 2 ? "Connect your first project" : "Connect your first provider";

  const submitStep = async () => {
    if (!data) return;
    if (step === 1 && !canAdvanceStepOne) return;
    if (step === 2 && !canAdvanceStepTwo) return;
    if (step === 3 && !canAdvanceStepThree) return;

    setError(null);
    setBusy(true);
    try {
      if (step === 1) {
        setStep(2);
        return;
      }
      if (step === 2) {
        await api.post("/api/projects", {
          ...project,
          name: project.name.trim(),
          repo_url: project.repo_url.trim(),
          local_clone_hint: project.local_clone_hint?.trim() || null,
        });
        await mutate("/api/projects");
        setStep(3);
        return;
      }

      await api.post("/api/providers", {
        ...provider,
        name: provider.name.trim(),
        api_key: provider.api_key?.trim() || undefined,
      });
      await mutate("/api/providers");
      await api.post("/api/workspaces/me/onboarding", { name: workspaceName.trim() });
      await mutate("/api/workspaces/me");
      setDismissed(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog.Root open={shouldShow} onOpenChange={(open) => { if (!open) setDismissed(true); }}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40" />
        <Dialog.Content
          className="fixed left-1/2 top-1/2 z-50 w-full max-w-2xl -translate-x-1/2 -translate-y-1/2 rounded-xl border border-gray-200 bg-white p-6 shadow-2xl focus:outline-none"
          aria-describedby={undefined}
        >
          <Flex justify="between" align="center" mb="3">
            <Dialog.Title asChild>
              <Text size="5" weight="bold">{stepTitle}</Text>
            </Dialog.Title>
            <Dialog.Close asChild>
              <Button variant="ghost" color="gray">Skip for now</Button>
            </Dialog.Close>
          </Flex>
        <Text size="2" color="gray">
          Step {step} of 3
        </Text>

        {step === 1 ? (
          <Flex direction="column" gap="2" mt="4">
            <Text size="2" weight="medium">Workspace name</Text>
            <TextField.Root
              placeholder="Acme Engineering"
              value={workspaceName}
              onChange={(event) => setWorkspaceName(event.target.value)}
            />
          </Flex>
        ) : null}

        {step === 2 ? (
          <Flex direction="column" gap="3" mt="4">
            <Field label="Project name">
              <TextField.Root
                value={project.name}
                onChange={(event) => setProject({ ...project, name: event.target.value })}
              />
            </Field>
            <Field label="Repository URL">
              <TextField.Root
                placeholder="https://github.com/org/repo"
                value={project.repo_url}
                onChange={(event) => setProject({ ...project, repo_url: event.target.value })}
              />
            </Field>
            <Flex gap="3">
              <Field label="SCM">
                <Select.Root
                  value={project.scm_kind}
                  onValueChange={(value) =>
                    setProject({ ...project, scm_kind: value as "github" | "gitlab" })
                  }
                >
                  <Select.Trigger />
                  <Select.Content>
                    <Select.Item value="github">GitHub</Select.Item>
                    <Select.Item value="gitlab">GitLab</Select.Item>
                  </Select.Content>
                </Select.Root>
              </Field>
              <Field label="Default branch">
                <TextField.Root
                  value={project.default_branch}
                  onChange={(event) =>
                    setProject({ ...project, default_branch: event.target.value || "main" })
                  }
                />
              </Field>
            </Flex>
          </Flex>
        ) : null}

        {step === 3 ? (
          <Flex direction="column" gap="3" mt="4">
            <Field label="Provider kind">
              <Select.Root
                value={provider.kind}
                onValueChange={(value) => {
                  const kind = value as "ollama" | "anthropic";
                  setProvider({
                    ...provider,
                    kind,
                    base_url: DEFAULT_PROVIDER_URL[kind],
                    name: kind === "ollama" ? "Local Ollama" : "Anthropic",
                  });
                }}
              >
                <Select.Trigger />
                <Select.Content>
                  <Select.Item value="ollama">ollama</Select.Item>
                  <Select.Item value="anthropic">anthropic</Select.Item>
                </Select.Content>
              </Select.Root>
            </Field>
            <Field label="Provider name">
              <TextField.Root
                value={provider.name}
                onChange={(event) => setProvider({ ...provider, name: event.target.value })}
              />
            </Field>
            <Field label="Base URL">
              <TextField.Root
                value={provider.base_url || ""}
                onChange={(event) =>
                  setProvider({ ...provider, base_url: event.target.value.trim() || null })
                }
              />
            </Field>
            {provider.kind === "anthropic" ? (
              <Field label="Anthropic API key">
                <TextField.Root
                  type="password"
                  placeholder="sk-ant-..."
                  value={provider.api_key || ""}
                  onChange={(event) => setProvider({ ...provider, api_key: event.target.value })}
                />
              </Field>
            ) : null}
          </Flex>
        ) : null}

        {error ? (
          <Text size="2" color="red" mt="3">
            {error}
          </Text>
        ) : null}

        <Flex mt="5" justify="between">
          <Button
            variant="soft"
            color="gray"
            disabled={busy || step === 1}
            onClick={() => setStep((prev) => (prev > 1 ? ((prev - 1) as Step) : prev))}
          >
            Back
          </Button>
          <Button
            onClick={submitStep}
            disabled={
              busy ||
              (step === 1 && !canAdvanceStepOne) ||
              (step === 2 && !canAdvanceStepTwo) ||
              (step === 3 && !canAdvanceStepThree)
            }
          >
            {busy ? "Working..." : step === 3 ? "Finish setup" : "Continue"}
          </Button>
        </Flex>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Flex direction="column" gap="1" style={{ flex: 1 }}>
      <Text size="2" color="gray" weight="medium">{label}</Text>
      {children}
    </Flex>
  );
}
