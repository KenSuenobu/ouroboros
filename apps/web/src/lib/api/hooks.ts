"use client";

import useSWR, { mutate } from "swr";
import { api } from "./client";
import type {
  Agent,
  Flow,
  Issue,
  McpRegistryEntry,
  McpServer,
  Project,
  Provider,
  ProviderHealth,
  ProviderModel,
  RoadmapEntry,
  Run,
  RunDetail,
  WorkspaceOnboardingStatus,
} from "./types";

const fetcher = <T,>(path: string) => api.get<T>(path);

export const useProjects = () => useSWR<Project[]>("/api/projects", fetcher);
export const useWorkspaceOnboarding = () =>
  useSWR<WorkspaceOnboardingStatus>("/api/workspaces/me", fetcher);
export const useProject = (id: string | null) => useSWR<Project>(id ? `/api/projects/${id}` : null, fetcher);
export const useIssues = (projectId: string | null, state = "open") =>
  useSWR<Issue[]>(projectId ? `/api/projects/${projectId}/issues?state=${state}` : null, fetcher);
export const useRoadmap = (projectId: string | null) =>
  useSWR<RoadmapEntry[]>(projectId ? `/api/projects/${projectId}/roadmap` : null, fetcher);
export const useProviders = () => useSWR<Provider[]>("/api/providers", fetcher);
export const useProviderHealth = (providerId: string | null) =>
  useSWR<ProviderHealth>(providerId ? `/api/providers/${providerId}/health` : null, fetcher);
export const useProviderModels = (providerId: string | null) =>
  useSWR<ProviderModel[]>(providerId ? `/api/providers/${providerId}/models` : null, fetcher);
export const useAgents = () => useSWR<Agent[]>("/api/agents", fetcher);
export const useFlows = () => useSWR<Flow[]>("/api/flows", fetcher);
export const useFlow = (id: string | null) => useSWR<Flow>(id ? `/api/flows/${id}` : null, fetcher);
export const useRuns = (projectId?: string | null) =>
  useSWR<Run[]>(projectId ? `/api/runs?project_id=${projectId}` : "/api/runs", fetcher);
export const useRun = (id: string | null) => useSWR<RunDetail>(id ? `/api/runs/${id}` : null, fetcher, { refreshInterval: 1500 });
export const useMcpServers = () => useSWR<McpServer[]>("/api/mcp/servers", fetcher);
export const useMcpRegistry = (q: string) =>
  useSWR<McpRegistryEntry[]>(`/api/mcp/registry?q=${encodeURIComponent(q)}`, fetcher);

export const refreshAll = (paths: string[]) => paths.forEach((p) => mutate(p));
