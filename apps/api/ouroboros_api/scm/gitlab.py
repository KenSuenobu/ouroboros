"""GitLab client: REST v4. Uses GITLAB_TOKEN env when present."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

import httpx

from .base import IssueRecord


class GitlabClient:
    def __init__(
        self, base_url: str = "https://gitlab.com", token_env: str = "GITLAB_TOKEN"
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = os.environ.get(token_env)

    def _client(self) -> httpx.AsyncClient:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["PRIVATE-TOKEN"] = self.token
        return httpx.AsyncClient(base_url=f"{self.base_url}/api/v4", headers=headers, timeout=20.0)

    @staticmethod
    def _project_path(repo: str) -> str:
        return quote(repo, safe="")

    async def list_issues(self, repo: str, *, state: str = "open", limit: int = 100) -> list[IssueRecord]:
        params = {"state": "opened" if state == "open" else state, "per_page": min(100, limit)}
        async with self._client() as client:
            r = await client.get(f"/projects/{self._project_path(repo)}/issues", params=params)
            r.raise_for_status()
            return [self._parse(item) for item in r.json()[:limit]]

    async def get_issue(self, repo: str, number: int) -> IssueRecord:
        async with self._client() as client:
            r = await client.get(f"/projects/{self._project_path(repo)}/issues/{number}")
            r.raise_for_status()
            return self._parse(r.json())

    async def comment_issue(self, repo: str, number: int, body: str) -> None:
        async with self._client() as client:
            r = await client.post(
                f"/projects/{self._project_path(repo)}/issues/{number}/notes", json={"body": body}
            )
            r.raise_for_status()

    async def open_pr(self, repo: str, *, title: str, body: str, head: str, base: str) -> str:
        async with self._client() as client:
            r = await client.post(
                f"/projects/{self._project_path(repo)}/merge_requests",
                json={"source_branch": head, "target_branch": base, "title": title, "description": body},
            )
            r.raise_for_status()
            return r.json().get("web_url", "")

    async def assign_pr_reviewer(self, repo: str, pr_number: int, reviewer: str) -> None:
        # GitLab requires a numeric user id; reviewer string is treated as username, looked up.
        async with self._client() as client:
            users = await client.get("/users", params={"username": reviewer})
            users.raise_for_status()
            user_list = users.json()
            if not user_list:
                return
            user_id = user_list[0]["id"]
            await client.put(
                f"/projects/{self._project_path(repo)}/merge_requests/{pr_number}",
                json={"reviewer_ids": [user_id]},
            )

    @staticmethod
    def _parse(item: dict[str, Any]) -> IssueRecord:
        state = item.get("state", "opened")
        return IssueRecord(
            number=item.get("iid", 0),
            title=item.get("title", ""),
            state="open" if state == "opened" else state,
            body=item.get("description"),
            labels=item.get("labels") or [],
            assignees=[a.get("username", "") for a in item.get("assignees") or []],
            milestone=(item.get("milestone") or {}).get("title")
            if isinstance(item.get("milestone"), dict)
            else item.get("milestone"),
            url=item.get("web_url"),
        )
