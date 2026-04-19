"""Pydantic schemas exposed by the REST API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class WorkspaceOut(_Base):
    id: str
    slug: str
    name: str
    created_at: datetime


class ProjectIn(_Base):
    name: str
    repo_url: str
    scm_kind: str = "github"
    default_branch: str = "main"
    local_clone_hint: str | None = None
    default_flow_id: str | None = None
    build_command: str | None = None
    test_command: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class ProjectOut(ProjectIn):
    id: str
    workspace_id: str
    created_at: datetime
    updated_at: datetime


class IssueOut(_Base):
    id: str
    project_id: str
    number: int
    title: str
    state: str
    body: str | None = None
    labels: list[Any] = Field(default_factory=list)
    assignees: list[Any] = Field(default_factory=list)
    milestone: str | None = None
    url: str | None = None
    last_synced_at: datetime | None = None


class RoadmapEntryOut(_Base):
    id: str
    project_id: str
    file_path: str
    section: str
    title: str
    body: str | None = None
    status: str
    kind: str


class IssueRoadmapPairIn(_Base):
    issue_id: str
    roadmap_entry_id: str
    confidence: float = 1.0
    source: str = "manual"


class IssueRoadmapPairOut(IssueRoadmapPairIn):
    id: str


class ProviderIn(_Base):
    name: str
    kind: str
    base_url: str | None = None
    api_key: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class ProviderOut(_Base):
    id: str
    workspace_id: str
    name: str
    kind: str
    base_url: str | None = None
    has_api_key: bool = False
    config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool


class ProviderModelOut(_Base):
    id: str
    provider_id: str
    model_id: str
    display_name: str | None = None
    capabilities: list[Any] = Field(default_factory=list)
    context_window: int | None = None
    input_cost_per_mtok: float | None = None
    output_cost_per_mtok: float | None = None
    last_seen_at: datetime | None = None


class ProviderChatRequest(_Base):
    model_id: str
    messages: list[dict[str, Any]]
    stream: bool = False
    max_tokens: int = 1024


class ProviderChatResponse(_Base):
    content: str
    model_used: str
    tokens_in: int = 0
    tokens_out: int = 0


class ModelPolicy(_Base):
    kind: str = "router"
    fixed_provider_id: str | None = None
    fixed_model_id: str | None = None
    router_hints: dict[str, Any] = Field(default_factory=dict)


class AgentToolBindingIn(_Base):
    tool_kind: str
    tool_ref: str
    config: dict[str, Any] = Field(default_factory=dict)


class AgentIn(_Base):
    name: str
    role: str
    description: str | None = None
    system_prompt: str = ""
    execution_adapter: str
    model_policy: ModelPolicy = Field(default_factory=ModelPolicy)
    config: dict[str, Any] = Field(default_factory=dict)
    dry_run_default: bool = False
    tool_bindings: list[AgentToolBindingIn] = Field(default_factory=list)


class AgentOut(_Base):
    id: str
    workspace_id: str
    name: str
    role: str
    description: str | None = None
    system_prompt: str
    execution_adapter: str
    model_policy: dict[str, Any]
    config: dict[str, Any]
    dry_run_default: bool
    is_builtin: bool
    tool_bindings: list[AgentToolBindingIn] = Field(default_factory=list)


class AgentTestRequest(_Base):
    input_text: str
    dry_run: bool = True
    provider_override_id: str | None = None
    model_override_id: str | None = None


class AgentTestResponse(_Base):
    output: str
    model_used: str
    tokens_in: int = 0
    tokens_out: int = 0
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class FlowIn(_Base):
    name: str
    description: str | None = None
    graph: dict[str, Any]
    is_default: bool = False


class FlowOut(_Base):
    id: str
    workspace_id: str
    name: str
    description: str | None = None
    graph: dict[str, Any]
    is_default: bool
    version: int


class McpServerOut(_Base):
    id: str
    workspace_id: str
    name: str
    registry_id: str | None = None
    transport: str
    install_spec: dict[str, Any]
    config: dict[str, Any]
    status: str
    side_effecting: bool


class McpRegistryEntry(_Base):
    id: str
    name: str
    description: str | None = None
    repository: str | None = None
    install: dict[str, Any] = Field(default_factory=dict)
    capabilities: list[str] = Field(default_factory=list)
    homepage: str | None = None


class McpInstallRequest(_Base):
    registry_id: str | None = None
    name: str
    transport: str = "stdio"
    install_spec: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    side_effecting: bool = False


class McpToolInvokeRequest(_Base):
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class RunStartRequest(_Base):
    project_id: str
    flow_id: str | None = None
    issue_id: str | None = None
    issue_number: int | None = None
    dry_run: bool = True
    override_models: dict[str, Any] = Field(default_factory=dict)
    title: str | None = None


class RunStepOut(_Base):
    id: str
    run_id: str
    node_id: str
    agent_id: str | None = None
    sequence: int
    attempt: int
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    provider_id: str | None = None
    model_used: str | None = None
    tokens_in: int
    tokens_out: int
    cost_estimate_usd: float
    summary: str | None = None
    error: str | None = None
    dry_run: bool


class RunOut(_Base):
    id: str
    workspace_id: str
    project_id: str
    flow_id: str
    issue_id: str | None = None
    issue_number: int | None = None
    title: str
    status: str
    dry_run: bool
    started_at: datetime | None = None
    finished_at: datetime | None = None
    total_tokens_in: int
    total_tokens_out: int
    cost_estimate_usd: float
    plan: dict[str, Any]
    error: str | None = None


class RunDetail(RunOut):
    steps: list[RunStepOut] = Field(default_factory=list)


class InterventionAnswer(_Base):
    answer: dict[str, Any]


class InterventionOut(_Base):
    id: str
    run_id: str
    run_step_id: str | None = None
    kind: str
    prompt: str
    options: list[Any]
    answer: dict[str, Any] | None = None
    status: str
    answered_at: datetime | None = None
