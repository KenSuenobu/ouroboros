"""SQLAlchemy 2.x models. Every domain row carries workspace_id for multi-tenant readiness."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, list[Any]: JSON}


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Workspace(Base, TimestampMixin):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    repo_url: Mapped[str] = mapped_column(String(500), nullable=False)
    scm_kind: Mapped[str] = mapped_column(String(32), default="github", nullable=False)
    default_branch: Mapped[str] = mapped_column(String(100), default="main", nullable=False)
    local_clone_hint: Mapped[str | None] = mapped_column(String(500))
    default_flow_id: Mapped[str | None] = mapped_column(ForeignKey("flows.id"))
    build_command: Mapped[str | None] = mapped_column(String(500))
    test_command: Mapped[str | None] = mapped_column(String(500))
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Issue(Base, TimestampMixin):
    __tablename__ = "issues"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True, nullable=False)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True, nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    state: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    labels: Mapped[list[Any]] = mapped_column(JSON, default=list)
    assignees: Mapped[list[Any]] = mapped_column(JSON, default=list)
    milestone: Mapped[str | None] = mapped_column(String(200))
    url: Mapped[str | None] = mapped_column(String(500))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (UniqueConstraint("project_id", "number", name="uq_issue_project_number"),)


class RoadmapEntry(Base, TimestampMixin):
    __tablename__ = "roadmap_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True, nullable=False)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True, nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    section: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="planned", nullable=False)
    kind: Mapped[str] = mapped_column(String(32), default="future", nullable=False)


class IssueRoadmapPair(Base, TimestampMixin):
    __tablename__ = "issue_roadmap_pairs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True, nullable=False)
    issue_id: Mapped[str] = mapped_column(ForeignKey("issues.id"), nullable=False)
    roadmap_entry_id: Mapped[str] = mapped_column(ForeignKey("roadmap_entries.id"), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)

    __table_args__ = (
        UniqueConstraint("issue_id", "roadmap_entry_id", name="uq_issue_roadmap_pair"),
    )


class Provider(Base, TimestampMixin):
    __tablename__ = "providers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(500))
    api_key_secret_ref: Mapped[str | None] = mapped_column(String(200))
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    models: Mapped[list[ProviderModel]] = relationship(
        back_populates="provider", cascade="all, delete-orphan"
    )


class ProviderModel(Base, TimestampMixin):
    __tablename__ = "provider_models"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True, nullable=False)
    provider_id: Mapped[str] = mapped_column(ForeignKey("providers.id"), nullable=False)
    model_id: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200))
    capabilities: Mapped[list[Any]] = mapped_column(JSON, default=list)
    context_window: Mapped[int | None] = mapped_column(Integer)
    input_cost_per_mtok: Mapped[float | None] = mapped_column(Float)
    output_cost_per_mtok: Mapped[float | None] = mapped_column(Float)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime)

    provider: Mapped[Provider] = relationship(back_populates="models")

    __table_args__ = (
        UniqueConstraint("provider_id", "model_id", name="uq_provider_model"),
    )


class Agent(Base, TimestampMixin):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    system_prompt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    execution_adapter: Mapped[str] = mapped_column(String(64), nullable=False)
    model_policy: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    dry_run_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    tool_bindings: Mapped[list[AgentToolBinding]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )


class AgentToolBinding(Base, TimestampMixin):
    __tablename__ = "agent_tool_bindings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True, nullable=False)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False)
    tool_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    tool_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    agent: Mapped[Agent] = relationship(back_populates="tool_bindings")


class McpServer(Base, TimestampMixin):
    __tablename__ = "mcp_servers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    registry_id: Mapped[str | None] = mapped_column(String(200))
    transport: Mapped[str] = mapped_column(String(16), default="stdio", nullable=False)
    install_spec: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="installed", nullable=False)
    side_effecting: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Flow(Base, TimestampMixin):
    __tablename__ = "flows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    graph: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class Run(Base, TimestampMixin):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True, nullable=False)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True, nullable=False)
    flow_id: Mapped[str] = mapped_column(ForeignKey("flows.id"), nullable=False)
    issue_id: Mapped[str | None] = mapped_column(ForeignKey("issues.id"))
    issue_number: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    total_tokens_in: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens_out: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_estimate_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    override_models: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    plan: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    sandbox_path: Mapped[str | None] = mapped_column(String(500))


class RunStep(Base, TimestampMixin):
    __tablename__ = "run_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True, nullable=False)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True, nullable=False)
    node_id: Mapped[str] = mapped_column(String(128), nullable=False)
    agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"))
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    provider_id: Mapped[str | None] = mapped_column(ForeignKey("providers.id"))
    model_used: Mapped[str | None] = mapped_column(String(200))
    tokens_in: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_estimate_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class RunArtifact(Base, TimestampMixin):
    __tablename__ = "run_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True, nullable=False)
    run_step_id: Mapped[str] = mapped_column(ForeignKey("run_steps.id"), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    content_ref: Mapped[str | None] = mapped_column(String(500))
    inline_content: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Intervention(Base, TimestampMixin):
    __tablename__ = "interventions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True, nullable=False)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True, nullable=False)
    run_step_id: Mapped[str | None] = mapped_column(ForeignKey("run_steps.id"))
    kind: Mapped[str] = mapped_column(String(32), default="question", nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list[Any]] = mapped_column(JSON, default=list)
    answer: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime)
