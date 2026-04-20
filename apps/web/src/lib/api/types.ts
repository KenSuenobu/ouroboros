// Type mirrors of the FastAPI Pydantic schemas. Kept handwritten so we don't need codegen at boot.

export type Workspace = {
  id: string;
  slug: string;
  name: string;
  onboarding_completed_at: string | null;
  created_at: string;
};

export type WorkspaceOnboardingStatus = {
  id: string;
  slug: string;
  name: string;
  onboarding_completed_at: string | null;
  project_count: number;
  provider_count: number;
  requires_onboarding: boolean;
};

export type Project = {
  id: string;
  workspace_id: string;
  name: string;
  repo_url: string;
  scm_kind: "github" | "gitlab";
  default_branch: string;
  local_clone_hint: string | null;
  default_flow_id: string | null;
  build_command: string | null;
  test_command: string | null;
  config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type ProjectInput = Omit<Project, "id" | "workspace_id" | "created_at" | "updated_at">;

export type Issue = {
  id: string;
  project_id: string;
  number: number;
  title: string;
  state: string;
  body: string | null;
  labels: string[];
  assignees: string[];
  milestone: string | null;
  url: string | null;
  last_synced_at: string | null;
};

export type RoadmapEntry = {
  id: string;
  project_id: string;
  file_path: string;
  section: string;
  title: string;
  body: string | null;
  status: string;
  kind: string;
};

export type IssueRoadmapPair = {
  id: string;
  issue_id: string;
  roadmap_entry_id: string;
  confidence: number;
  source: string;
};

export type Provider = {
  id: string;
  workspace_id: string;
  name: string;
  kind: "ollama" | "anthropic" | "github_models" | "opencode" | "gh_copilot";
  base_url: string | null;
  has_api_key: boolean;
  config: Record<string, unknown>;
  enabled: boolean;
  last_health_status: "ok" | "unreachable" | "unauthorized" | "no-models" | "unsupported" | null;
  last_health_error: string | null;
  last_health_checked_at: string | null;
};

export type ProviderInput = Omit<
  Provider,
  "id" | "workspace_id" | "has_api_key" | "last_health_status" | "last_health_error" | "last_health_checked_at"
> & {
  api_key?: string;
};

export type ProviderModel = {
  id: string;
  provider_id: string;
  model_id: string;
  display_name: string | null;
  capabilities: string[];
  context_window: number | null;
  input_cost_per_mtok: number | null;
  output_cost_per_mtok: number | null;
  last_seen_at: string | null;
};

export type ProviderHealth = {
  provider_id: string;
  status: "ok" | "unreachable" | "unauthorized" | "no-models" | "unsupported";
  error: string | null;
  checked_at: string;
};

export type ModelPolicy = {
  kind: "fixed" | "router" | "user_pick";
  fixed_provider_id?: string | null;
  fixed_model_id?: string | null;
  router_hints?: Record<string, unknown>;
};

export type AgentToolBinding = {
  tool_kind: string;
  tool_ref: string;
  config: Record<string, unknown>;
};

export type Agent = {
  id: string;
  workspace_id: string;
  name: string;
  role: string;
  description: string | null;
  system_prompt: string;
  execution_adapter: string;
  model_policy: ModelPolicy;
  config: Record<string, unknown>;
  dry_run_default: boolean;
  is_builtin: boolean;
  tool_bindings: AgentToolBinding[];
};

export type AgentInput = Omit<Agent, "id" | "workspace_id" | "is_builtin">;

export type Flow = {
  id: string;
  workspace_id: string;
  name: string;
  description: string | null;
  graph: { nodes: FlowNode[]; edges: FlowEdge[] };
  is_default: boolean;
  version: number;
};

export type FlowNode = {
  id: string;
  type: "agent" | "wait_for_user" | "condition" | "parallel";
  agent_role?: string;
  label: string;
  position: { x: number; y: number };
  config?: Record<string, unknown>;
};

export type FlowEdge = {
  id: string;
  source: string;
  target: string;
  condition?: string;
  label?: string;
};

export type McpRegistryEntry = {
  id: string;
  name: string;
  description: string | null;
  repository: string | null;
  install: Record<string, unknown>;
  capabilities: string[];
  homepage: string | null;
};

export type McpServer = {
  id: string;
  workspace_id: string;
  name: string;
  registry_id: string | null;
  transport: "stdio" | "http";
  install_spec: Record<string, unknown>;
  config: Record<string, unknown>;
  status: string;
  side_effecting: boolean;
};

export type RunStep = {
  id: string;
  run_id: string;
  node_id: string;
  agent_id: string | null;
  sequence: number;
  attempt: number;
  status: "pending" | "running" | "succeeded" | "failed" | "cancelled" | string;
  started_at: string | null;
  finished_at: string | null;
  provider_id: string | null;
  model_used: string | null;
  tokens_in: number;
  tokens_out: number;
  cost_estimate_usd: number;
  summary: string | null;
  error: string | null;
  dry_run: boolean;
};

export type Run = {
  id: string;
  workspace_id: string;
  project_id: string;
  flow_id: string;
  issue_id: string | null;
  issue_number: number | null;
  title: string;
  status: "pending" | "running" | "succeeded" | "failed" | "cancelled" | string;
  dry_run: boolean;
  started_at: string | null;
  finished_at: string | null;
  total_tokens_in: number;
  total_tokens_out: number;
  cost_estimate_usd: number;
  plan: { nodes?: FlowNode[]; edges?: FlowEdge[] };
  error: string | null;
};

export type RunDetail = Run & { steps: RunStep[] };

export type Intervention = {
  id: string;
  run_id: string;
  run_step_id: string | null;
  kind: string;
  prompt: string;
  options: Array<{ id: string; label: string }>;
  answer: Record<string, unknown> | null;
  status: "pending" | "answered" | "skipped" | string;
  answered_at: string | null;
};

export type RunEvent = {
  run_id: string;
  type: string;
  payload: Record<string, unknown>;
  timestamp: string;
};
