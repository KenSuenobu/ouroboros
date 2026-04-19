"""Built-in (no-LLM) agent adapter for SCM, branch, build, test, and commit nodes."""

from __future__ import annotations

import json
from typing import Any

from ...sandbox.shell import run_shell
from ...scm import get_client
from ...scm.base import repo_slug
from ..base import ResolvedModel, StepResult


class BuiltinAgentAdapter:
    name = "builtin"

    async def run(self, ctx: Any, agent: Any, model: ResolvedModel) -> StepResult:
        builtin = (agent.config or {}).get("builtin", "")
        try:
            handler = getattr(self, f"_h_{builtin.replace('.', '_')}")
        except AttributeError:
            return StepResult(
                summary=f"unknown builtin {builtin!r}",
                failed=True,
                error=f"unknown builtin {builtin!r}",
            )
        return await handler(ctx, agent)

    async def _h_issue_fetch(self, ctx: Any, agent: Any) -> StepResult:
        if not ctx.project or not ctx.run.issue_number:
            return StepResult(summary="no issue number", failed=True, error="no issue number on run")
        client = get_client(ctx.project)
        try:
            rec = await client.get_issue(repo_slug(ctx.project), ctx.run.issue_number)
        except Exception as exc:
            return StepResult(summary="issue fetch failed", failed=True, error=str(exc))
        ctx.issue = {
            "number": rec.number,
            "title": rec.title,
            "state": rec.state,
            "body": rec.body,
            "labels": rec.labels,
            "url": rec.url,
        }
        ctx.scratchpad["agent_input"] = (
            f"Issue #{rec.number}: {rec.title}\n\nLabels: {', '.join(rec.labels) or '(none)'}\n\n{rec.body or ''}"
        )
        return StepResult(
            summary=f"Fetched issue #{rec.number}: {rec.title}",
            output=ctx.issue,
            artifacts=[
                {"kind": "response", "name": "issue.json", "inline_content": json.dumps(ctx.issue, default=str, indent=2)}
            ],
        )

    async def _h_git_branch(self, ctx: Any, agent: Any) -> StepResult:
        template = (agent.config or {}).get("branch_template", "ticket-{number}")
        number = ctx.run.issue_number or 0
        branch = template.format(number=number, run_id=ctx.run.id)
        result = await run_shell(
            f"git checkout -b {branch}", cwd=ctx.sandbox_path, dry_run=False
        )
        ctx.scratchpad["branch"] = branch
        if not result.succeeded and "already exists" in result.stderr:
            await run_shell(f"git checkout {branch}", cwd=ctx.sandbox_path, dry_run=False)
        return StepResult(
            summary=f"Branch ready: {branch}",
            output={"branch": branch},
            artifacts=[{"kind": "shell_log", "name": "git.checkout", "inline_content": result.stdout + result.stderr}],
        )

    async def _h_shell_build(self, ctx: Any, agent: Any) -> StepResult:
        cmd = ctx.project.build_command if ctx.project else None
        if not cmd:
            return StepResult(summary="no build command configured", warnings=["no build command"])
        result = await run_shell(cmd, cwd=ctx.sandbox_path, dry_run=False, timeout=900.0)
        ctx.scratchpad["build_passed"] = result.succeeded
        return StepResult(
            summary=("build passed" if result.succeeded else "build failed"),
            output={"exit_code": result.exit_code},
            artifacts=[
                {"kind": "shell_log", "name": "build.stdout", "inline_content": result.stdout[-20000:]},
                {"kind": "shell_log", "name": "build.stderr", "inline_content": result.stderr[-20000:]},
            ],
            failed=not result.succeeded,
            error=None if result.succeeded else (result.stderr or result.stdout)[-2000:],
        )

    async def _h_shell_test(self, ctx: Any, agent: Any) -> StepResult:
        cmd = ctx.project.test_command if ctx.project else None
        if not cmd:
            return StepResult(summary="no test command configured", warnings=["no test command"])
        result = await run_shell(cmd, cwd=ctx.sandbox_path, dry_run=False, timeout=1800.0)
        ctx.scratchpad["tests_passed"] = result.succeeded
        return StepResult(
            summary=("tests passed" if result.succeeded else "tests failed"),
            output={"exit_code": result.exit_code, "passed": result.succeeded},
            artifacts=[
                {"kind": "shell_log", "name": "test.stdout", "inline_content": result.stdout[-20000:]},
                {"kind": "shell_log", "name": "test.stderr", "inline_content": result.stderr[-20000:]},
            ],
            failed=not result.succeeded,
            error=None if result.succeeded else (result.stderr or result.stdout)[-2000:],
        )

    async def _h_scm_commit_and_pr(self, ctx: Any, agent: Any) -> StepResult:
        if ctx.dry_run:
            return StepResult(
                summary="commit + pr suppressed in dry-run",
                warnings=["side-effecting step skipped"],
            )
        number = ctx.run.issue_number or 0
        title = ctx.run.title or f"Fix #{number}"
        await run_shell("git add -A", cwd=ctx.sandbox_path, dry_run=False)
        await run_shell(
            f'git commit -m "Fix #{number} - {title}"', cwd=ctx.sandbox_path, dry_run=False
        )
        branch = ctx.scratchpad.get("branch", f"ticket-{number}")
        await run_shell(
            f"git push origin {branch}", cwd=ctx.sandbox_path, dry_run=False, allow_side_effect=True
        )
        client = get_client(ctx.project)
        try:
            url = await client.open_pr(
                repo_slug(ctx.project),
                title=f"Fix #{number} - {title}",
                body=f"Closes #{number}.\n\nGenerated by Ouroboros.",
                head=branch,
                base=ctx.project.default_branch,
            )
        except Exception as exc:
            return StepResult(summary="pr open failed", failed=True, error=str(exc))
        ctx.scratchpad["pr_url"] = url
        return StepResult(summary=f"PR opened: {url}", output={"pr_url": url})

    async def _h_scm_assign_reviewer(self, ctx: Any, agent: Any) -> StepResult:
        if ctx.dry_run:
            return StepResult(summary="reviewer assignment suppressed in dry-run")
        url = ctx.scratchpad.get("pr_url", "")
        # Extract PR number from URL.
        try:
            pr_number = int(url.rstrip("/").split("/")[-1])
        except Exception:
            return StepResult(summary="no pr to assign", warnings=["pr_url missing or unparseable"])
        reviewer = (agent.config or {}).get("reviewer", "copilot")
        client = get_client(ctx.project)
        try:
            await client.assign_pr_reviewer(repo_slug(ctx.project), pr_number, reviewer)
        except Exception as exc:
            return StepResult(summary="assign failed", failed=True, error=str(exc))
        return StepResult(summary=f"Reviewer {reviewer} assigned to PR #{pr_number}")

    async def _h_scm_comment_issue(self, ctx: Any, agent: Any) -> StepResult:
        if ctx.dry_run:
            return StepResult(summary="issue comment suppressed in dry-run")
        template = (agent.config or {}).get("template", "Work completed as directed")
        number = ctx.run.issue_number or 0
        client = get_client(ctx.project)
        try:
            await client.comment_issue(repo_slug(ctx.project), number, template)
        except Exception as exc:
            return StepResult(summary="comment failed", failed=True, error=str(exc))
        return StepResult(summary=f"Commented on issue #{number}")
