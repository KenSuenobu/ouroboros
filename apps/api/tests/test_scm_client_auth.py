from __future__ import annotations

from ouroboros_api.db.models import Project
from ouroboros_api.scm.base import get_client
from ouroboros_api.scm.github import GithubClient
from ouroboros_api.scm.gitlab import GitlabClient


def _project(*, scm_kind: str, token: str | None) -> Project:
    config = {}
    if token:
        config["repo_access_token"] = token
    return Project(
        workspace_id="ws-1",
        name="Demo",
        repo_url="https://github.com/acme/demo",
        scm_kind=scm_kind,
        default_branch="main",
        config=config,
    )


def test_get_client_prefers_project_token_for_github() -> None:
    client = get_client(_project(scm_kind="github", token="ghp_project"))
    assert isinstance(client, GithubClient)
    assert client.token == "ghp_project"


def test_get_client_prefers_project_token_for_gitlab() -> None:
    client = get_client(_project(scm_kind="gitlab", token="gl_project"))
    assert isinstance(client, GitlabClient)
    assert client.token == "gl_project"
