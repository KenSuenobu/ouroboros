"""SCM client abstraction: GitHub or GitLab."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ..db.models import Project


@dataclass
class IssueRecord:
    number: int
    title: str
    state: str
    body: str | None = None
    labels: list[str] = field(default_factory=list)
    assignees: list[str] = field(default_factory=list)
    milestone: str | None = None
    url: str | None = None


class ScmClient(Protocol):
    async def list_issues(self, repo: str, *, state: str = "open", limit: int = 100) -> list[IssueRecord]: ...
    async def get_issue(self, repo: str, number: int) -> IssueRecord: ...
    async def comment_issue(self, repo: str, number: int, body: str) -> None: ...
    async def open_pr(self, repo: str, *, title: str, body: str, head: str, base: str) -> str: ...
    async def assign_pr_reviewer(self, repo: str, pr_number: int, reviewer: str) -> None: ...


def get_client(project: Project) -> ScmClient:
    from .github import GithubClient
    from .gitlab import GitlabClient

    if project.scm_kind == "gitlab":
        return GitlabClient()
    return GithubClient()


def repo_slug(project: Project) -> str:
    """Extract owner/repo from a repo URL."""
    url = project.repo_url.rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    parts = url.split("/")
    if len(parts) >= 2:
        return f"{parts[-2]}/{parts[-1]}"
    return url
