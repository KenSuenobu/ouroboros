"""Default agents that map to the /implement workflow nodes."""

from __future__ import annotations

from typing import Any

DEFAULT_AGENTS: list[dict[str, Any]] = [
    {
        "name": "Issue Fetcher",
        "role": "issue.fetcher",
        "description": "Fetches the target issue via gh / GitLab REST. No LLM call.",
        "system_prompt": "",
        "execution_adapter": "builtin",
        "model_policy": {"kind": "fixed"},
        "config": {"builtin": "issue.fetch"},
    },
    {
        "name": "Issue Summarizer",
        "role": "issue.summarizer",
        "description": "Summarizes the issue, surfaces ambiguity, proposes clarifying questions.",
        "system_prompt": (
            "You are reviewing a GitHub/GitLab issue. Produce a concise summary of intent, "
            "list any ambiguities, and propose clarifying questions if requirements are "
            "unclear or contradict the codebase. Output JSON: "
            '{"summary":..., "questions":[...], "risk":"low|medium|high"}.'
        ),
        "execution_adapter": "anthropic_api",
        "model_policy": {"kind": "router", "router_hints": {"prefer": "reasoning"}},
        "config": {},
    },
    {
        "name": "Branch Setup",
        "role": "branch.setup",
        "description": "Creates ticket-<n> branch in the sandbox clone.",
        "system_prompt": "",
        "execution_adapter": "builtin",
        "model_policy": {"kind": "fixed"},
        "config": {"builtin": "git.branch", "branch_template": "ticket-{number}"},
    },
    {
        "name": "Planner",
        "role": "planner",
        "description": "Produces a structured plan: file list, risk, test plan.",
        "system_prompt": (
            "You are the planning agent. Read the summarized issue and the relevant repo "
            "context, then output a structured plan: target files, code changes, risks, "
            "and a test plan. Output strict JSON."
        ),
        "execution_adapter": "anthropic_api",
        "model_policy": {"kind": "router", "router_hints": {"prefer": "reasoning"}},
        "config": {},
    },
    {
        "name": "Coder",
        "role": "coder",
        "description": "Applies the plan to the codebase. Routes per dominant language.",
        "system_prompt": (
            "You are the implementation agent. Apply the plan precisely. Use the available "
            "tools (read_file, write_file, run_shell). Keep changes minimal and tested."
        ),
        "execution_adapter": "ollama_api",
        "model_policy": {
            "kind": "router",
            "router_hints": {
                "language_map": {
                    "python": {"prefer_kind": "ollama", "model_hint": "qwen2.5-coder"},
                    "typescript": {"prefer_kind": "anthropic", "model_hint": "claude-sonnet"},
                    "javascript": {"prefer_kind": "anthropic", "model_hint": "claude-sonnet"},
                    "sql": {"prefer_kind": "ollama", "model_hint": "sqlcoder"},
                    "rust": {"prefer_kind": "ollama", "model_hint": "qwen2.5-coder"}
                }
            }
        },
        "config": {},
    },
    {
        "name": "Internal Audit",
        "role": "internal.audit",
        "description": "Reviews the diff for misuses, missing tests, hard-coded values.",
        "system_prompt": (
            "You are the audit agent. Review the diff for safety, test coverage, "
            "hard-coded values (colors, secrets), DRY violations, and unclear naming. "
            "Output a list of findings with severity."
        ),
        "execution_adapter": "anthropic_api",
        "model_policy": {"kind": "router", "router_hints": {"prefer": "reasoning"}},
        "config": {},
    },
    {
        "name": "Build Verifier",
        "role": "verify.build",
        "description": "Runs the project build command. Captures full log.",
        "system_prompt": "",
        "execution_adapter": "builtin",
        "model_policy": {"kind": "fixed"},
        "config": {"builtin": "shell.build"},
    },
    {
        "name": "Test Verifier",
        "role": "verify.test",
        "description": "Runs the project test command. Surfaces failure context.",
        "system_prompt": "",
        "execution_adapter": "builtin",
        "model_policy": {"kind": "fixed"},
        "config": {"builtin": "shell.test"},
    },
    {
        "name": "Notes Updater",
        "role": "notes.updater",
        "description": "Updates ROADMAP / WHATS_NEW and bumps version per project rules.",
        "system_prompt": (
            "Update roadmap entries marked complete by the issue, append a one-line "
            "WHATS_NEW entry, and bump the patch version of any package whose code changed."
        ),
        "execution_adapter": "anthropic_api",
        "model_policy": {"kind": "router"},
        "config": {},
    },
    {
        "name": "Commit & Push",
        "role": "commit.push",
        "description": "git add/commit/push and gh pr create. Skipped in dry-run.",
        "system_prompt": "",
        "execution_adapter": "builtin",
        "model_policy": {"kind": "fixed"},
        "config": {"builtin": "scm.commit_and_pr"},
    },
    {
        "name": "PR Reviewer Assign",
        "role": "pr.reviewer.assign",
        "description": "Assigns Copilot (or configured reviewer) to the PR.",
        "system_prompt": "",
        "execution_adapter": "builtin",
        "model_policy": {"kind": "fixed"},
        "config": {"builtin": "scm.assign_reviewer", "reviewer": "copilot"},
    },
    {
        "name": "Issue Commenter",
        "role": "issue.commenter",
        "description": "Posts the completion comment on the original issue.",
        "system_prompt": "",
        "execution_adapter": "builtin",
        "model_policy": {"kind": "fixed"},
        "config": {"builtin": "scm.comment_issue", "template": "Work completed as directed"},
    },
    {
        "name": "Router",
        "role": "router",
        "description": "Suggests the best provider+model for each downstream agent step.",
        "system_prompt": (
            "You are the routing agent. Given the issue, the planner output (when available), "
            "and the inventory of providers/models, suggest the best provider+model for each "
            "downstream agent that has model_policy.kind == 'router'. Output strict JSON: "
            '{"<agent_role>": {"provider_id": "...", "model_id": "...", "reason": "..."}}.'
        ),
        "execution_adapter": "anthropic_api",
        "model_policy": {"kind": "router"},
        "config": {},
    },
]
