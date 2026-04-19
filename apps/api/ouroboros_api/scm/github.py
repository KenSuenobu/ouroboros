"""GitHub client: prefers `gh` CLI when available, falls back to REST."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from typing import Any

import httpx

from .base import IssueRecord


def _gh_available() -> bool:
    return shutil.which("gh") is not None


class GithubClient:
    def __init__(self, token_env: str = "GITHUB_TOKEN") -> None:
        self.token = os.environ.get(token_env)

    async def _gh(self, *args: str) -> str:
        proc = await asyncio.create_subprocess_exec(
            "gh", *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        out, err = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"gh failed: {err.decode().strip()}")
        return out.decode()

    async def _http(self) -> httpx.AsyncClient:
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return httpx.AsyncClient(base_url="https://api.github.com", headers=headers, timeout=20.0)

    async def list_issues(
        self, repo: str, *, state: str = "open", limit: int = 100
    ) -> list[IssueRecord]:
        if _gh_available():
            raw = await self._gh(
                "issue", "list", "--repo", repo, "--state", state, "--limit", str(limit),
                "--json", "number,title,state,body,labels,assignees,milestone,url",
            )
            data = json.loads(raw)
            return [self._parse_gh_issue(item) for item in data]
        async with await self._http() as client:
            r = await client.get(f"/repos/{repo}/issues", params={"state": state, "per_page": min(100, limit)})
            r.raise_for_status()
            data = [i for i in r.json() if "pull_request" not in i]
            return [self._parse_rest_issue(item) for item in data[:limit]]

    async def get_issue(self, repo: str, number: int) -> IssueRecord:
        if _gh_available():
            raw = await self._gh(
                "issue", "view", str(number), "--repo", repo,
                "--json", "number,title,state,body,labels,assignees,milestone,url",
            )
            return self._parse_gh_issue(json.loads(raw))
        async with await self._http() as client:
            r = await client.get(f"/repos/{repo}/issues/{number}")
            r.raise_for_status()
            return self._parse_rest_issue(r.json())

    async def comment_issue(self, repo: str, number: int, body: str) -> None:
        if _gh_available():
            await self._gh("issue", "comment", str(number), "--repo", repo, "--body", body)
            return
        async with await self._http() as client:
            r = await client.post(f"/repos/{repo}/issues/{number}/comments", json={"body": body})
            r.raise_for_status()

    async def open_pr(self, repo: str, *, title: str, body: str, head: str, base: str) -> str:
        if _gh_available():
            out = await self._gh(
                "pr", "create", "--repo", repo, "--title", title, "--body", body,
                "--head", head, "--base", base,
            )
            return out.strip().splitlines()[-1]
        async with await self._http() as client:
            r = await client.post(
                f"/repos/{repo}/pulls", json={"title": title, "body": body, "head": head, "base": base}
            )
            r.raise_for_status()
            return r.json().get("html_url", "")

    async def assign_pr_reviewer(self, repo: str, pr_number: int, reviewer: str) -> None:
        if _gh_available():
            await self._gh("pr", "edit", str(pr_number), "--repo", repo, "--add-reviewer", reviewer)
            return
        async with await self._http() as client:
            r = await client.post(
                f"/repos/{repo}/pulls/{pr_number}/requested_reviewers",
                json={"reviewers": [reviewer]},
            )
            r.raise_for_status()

    @staticmethod
    def _parse_gh_issue(item: dict[str, Any]) -> IssueRecord:
        return IssueRecord(
            number=item.get("number", 0),
            title=item.get("title", ""),
            state=item.get("state", "open").lower(),
            body=item.get("body"),
            labels=[lbl.get("name", "") if isinstance(lbl, dict) else lbl for lbl in item.get("labels") or []],
            assignees=[
                u.get("login", "") if isinstance(u, dict) else u for u in item.get("assignees") or []
            ],
            milestone=(item.get("milestone") or {}).get("title") if isinstance(item.get("milestone"), dict) else item.get("milestone"),
            url=item.get("url"),
        )

    @staticmethod
    def _parse_rest_issue(item: dict[str, Any]) -> IssueRecord:
        return IssueRecord(
            number=item.get("number", 0),
            title=item.get("title", ""),
            state=item.get("state", "open"),
            body=item.get("body"),
            labels=[lbl.get("name", "") for lbl in item.get("labels", [])],
            assignees=[u.get("login", "") for u in item.get("assignees", [])],
            milestone=(item.get("milestone") or {}).get("title"),
            url=item.get("html_url"),
        )
