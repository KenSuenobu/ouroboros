# Ouroboros — Planned Feature Roadmap (2026)

This roadmap captures every feature that surfaced while implementing the
v0.1 design but was deliberately deferred. Each entry is a candidate GitHub
issue. Once this repo is on GitHub, run `scripts/seed_issues.sh` (see the
last section) and the `Issue` column will be populated.

The list is ordered by **development stage**: MVP first, then post-MVP, then
the explicitly Enterprise-only items. Within each stage, items are roughly
sequenced by dependency.

Legend
- **MVP** — required for the first usable release ("`/implement` an issue end-to-end on a single project, locally, with one provider").
- **Post-MVP** — required to make the product pleasant for daily use.
- **Enterprise** — only relevant to multi-tenant cloud or on-prem enterprise installs.

Completed
- #67 - Added system-aware light/dark mode with a top-right header toggle in the web app.
- #7 - Added a first-run onboarding wizard for workspace setup, initial project connection, and first provider setup.
- #9 - Added repository command introspection to suggest build/test commands in the project editor.
- #10 - Added per-language router policy defaults to all seed router agents.
- #11 - Added real-time stdout/stderr streaming for shell steps with step-level live logs.

---


## Epics

- #1 - Stage 1 - MVP correctness & onboarding
- #2 - Stage 2 - UX & power-user features
- #3 - Stage 3 - Quality, observability, operability
- #4 - Stage 4 - Cloud (Solo / Team)
- #5 - Stage 5 - Enterprise
- #6 - Stretch / research
## Stage 1 — MVP correctness & onboarding

| #     | Issue                                                                                          | Tier | Notes                                                    |
|-------|------------------------------------------------------------------------------------------------|------|----------------------------------------------------------|
| #8 | Healthcheck panel: ping each configured provider, surface "needs key" / "ollama unreachable"   | MVP  | New `GET /api/providers/{id}/health` and a `/health` page       |
| #12 | Persisted `.env` for `OUROBOROS_DB_URL` etc. via `ouroboros init` CLI                          | MVP  | Today envs are read but never written for the user               |
| #13 | "Resume" button when a run was interrupted by a crash mid-step                                 | MVP  | Engine has `attempts` but no resume from prior step              |
| #14 | Robust dry-run diff viewer: real side-by-side using Monaco's `DiffEditor`                      | MVP  | Current `DiffViewer` is a thin wrapper; needs left/right inputs  |

## Stage 2 — UX & power-user features

| #     | Issue                                                                                          | Tier      | Notes                                                |
|-------|------------------------------------------------------------------------------------------------|-----------|------------------------------------------------------|
| #15 | Side-by-side run comparison view (pick two runs → diff their plans, costs, artifacts)         | Post-MVP  | Useful for A/B testing two model policies            |
| #16 | Cost forecast on the "Run this issue" button (estimate tokens before clicking)                 | Post-MVP  | Uses average per-step token counts from history      |
| #17 | Saved router presets ("frontend stack", "data eng stack") shared across agents                 | Post-MVP  | Currently router hints are per-agent JSON            |
| #18 | Inline issue triage: rewrite acceptance criteria from the UI before kicking off the run        | Post-MVP  | Editable issue body that flows into the planner      |
| #19 | Multi-issue batch runs (queue 5 issues, watch them progress in parallel with global cap)       | Post-MVP  | Engine already supports concurrent runs              |
| #20 | Notification adapters: webhook, Slack, email, Linear comment when a run finishes               | Post-MVP  | New `NotificationAdapter` ABC                        |
| #21 | Project-level "do not auto-merge" / "require human approval" rule on the flow graph            | Post-MVP  | Adds a `require_approval` node type                  |
| #22 | Diff-aware planner: Planner gets a structured repo summary (file tree + recent commits)        | Post-MVP  | Reduces token cost vs. dumping the whole repo        |
| #23 | Sandbox snapshotting: copy-on-write `git worktree`-backed sandbox per run                      | Post-MVP  | Faster than full re-clone for big repos              |
| #24 | Local artifact storage GC (LRU eviction beyond N GB)                                            | Post-MVP  | Prevents `data/runs/` from filling disk              |
| #25 | Provider failover: if Anthropic 5xx mid-run, retry on a routed Ollama equivalent               | Post-MVP  | Engine retry hook exists; provider routing does not  |
| #26 | First-class GitLab support parity (issue body markdown render, MR comments, pipelines)         | Post-MVP  | Today GitLab is functional but UI-light              |
| #27 | First-class Bitbucket Cloud + Bitbucket DC adapter                                              | Post-MVP  | Needed for many regulated shops                      |
| #28 | Roadmap-aware planner: pull the matched roadmap entry into the planner system prompt           | Post-MVP  | We already produce pairs; we don't yet consume them  |
| #29 | Inline MCP tool inspector (right pane in Run detail showing each tool call as it happens)      | Post-MVP  | Useful for debugging long agent loops                |
| #30 | "Replay" mode: re-run a failed step against a different model without restarting the whole run | Post-MVP  | Hot-swap model on a single step                      |
| #31 | Convert any successful run into a reusable Flow template ("save as flow")                      | Post-MVP  | Closes the design loop: run → flow → run             |

## Stage 3 — Quality, observability, and operability

| #     | Issue                                                                                          | Tier      | Notes                                                |
|-------|------------------------------------------------------------------------------------------------|-----------|------------------------------------------------------|
| #32 | Structured JSON event log → file rotation in `data/logs/` with `structlog` JSON renderer       | Post-MVP  | Today we log to stderr only                          |
| #33 | Prometheus `/metrics` endpoint (run rates, token spend, intervention age, MCP failure rate)    | Post-MVP  | Hosted instances need this                           |
| #34 | OpenTelemetry tracing for each agent step (provider, model, latency, tokens) → OTLP exporter   | Post-MVP  | Instrument the engine + adapters                     |
| #35 | Backup / restore CLI (`ouroboros backup`, `ouroboros restore`)                                 | Post-MVP  | SQLite + `data/runs/` tarball                        |
| #36 | Migration story: SQLite → Postgres single command                                              | Post-MVP  | First step toward Cloud Solo                         |
| #37 | Fuzz tests for `classify_command` (random shell commands → expected category)                  | Post-MVP  | Hardens the dry-run guarantee                        |
| #38 | Adversarial test pack: prompt-injection issues that try to escape the sandbox                  | Post-MVP  | Run weekly in CI                                     |
| #39 | Provider rate-limit-aware backpressure (Anthropic 429 → exponential pause)                     | Post-MVP  | Avoids burning a session on rate limits              |
| #40 | Configurable model price catalog (load `provider_prices.yaml` so cost stays current)           | Post-MVP  | Today prices are inferred from provider API only     |

## Stage 4 — Cloud (Solo / Team)

| #     | Issue                                                                                          | Tier      | Notes                                                |
|-------|------------------------------------------------------------------------------------------------|-----------|------------------------------------------------------|
| #41 | Auth: GitHub OAuth + email magic link login                                                    | Cloud     | Lives in private `ouroboros-cloud` package           |
| #42 | Workspace invites + role assignment (owner / maintainer / runner / viewer)                     | Cloud     | RBAC enforcement on every router                    |
| #43 | Org-shared providers (admin sets key, members consume; key never returned to client)           | Cloud     | Reuses `SecretsBackend(VaultBackend)`                |
| #44 | Stripe metered billing wiring (`RunMeter` aggregator + nightly reconcile job)                  | Cloud     | Detailed in `BUSINESS_MODEL.md` §4                   |
| #45 | Managed Models proxy: outbound reseller for Anthropic / OpenAI / Bedrock with caching          | Cloud     | Optional add-on, gated per workspace                 |
| #46 | S3-compatible artifact storage backend (`ArtifactStore` ABC)                                   | Cloud     | Today artifacts live on local disk                   |
| #47 | Audit log export (S3 / GCS / webhook) with daily delivery                                      | Cloud     | Compliance-grade tamper-evident log                  |
| #48 | Webhook delivery for `run.*` events with HMAC signing + retry                                  | Cloud     | Replaces in-process bus for external listeners       |
| #49 | Public REST API tokens (separate from session) with per-token rate limiting                    | Cloud     | Programmatic CI integrations                         |

## Stage 5 — Enterprise

| #     | Issue                                                                                          | Tier        | Notes                                              |
|-------|------------------------------------------------------------------------------------------------|-------------|----------------------------------------------------|
| #50 | SAML / OIDC SSO with JIT provisioning                                                          | Enterprise  | Required to cross the $50k/yr line                 |
| #51 | SCIM 2.0 user / group provisioning                                                             | Enterprise  | Sync from Okta / Azure AD                          |
| #52 | Customer-managed KMS for `SecretsBackend` (BYOK)                                               | Enterprise  | AWS KMS, GCP KMS, HashiCorp Vault                  |
| #53 | Air-gapped deploy mode (Ollama-only routing enforced; no outbound calls from agents)           | Enterprise  | Hard-fails if any adapter would dial the internet  |
| #54 | Policy engine: OPA/Rego rules per workspace (e.g. "never run on `prod/*` branches")            | Enterprise  | Evaluated at flow start + before each side-effect  |
| #55 | Data residency selector (workspace pinned to a region; data never leaves)                      | Enterprise  | Required for EU / APAC                             |
| #56 | Customer-managed CA + mTLS between API ↔ web ↔ MCP servers                                     | Enterprise  | For regulated networks                             |
| #57 | Tamper-evident append-only audit log (Merkle-chained event log; daily root signed and shipped) | Enterprise  | SOX-friendly                                       |
| #58 | Long-form retention policies per data class (artifacts 90d, audit 7y, prompts 0d)              | Enterprise  | Configurable, per-tenant                           |
| #59 | Helm chart + Terraform module for self-hosted deployment                                       | Enterprise  | Targets EKS, GKE, AKS, OpenShift                   |
| #60 | Customer-managed model gateway (terminate at customer's existing LLM proxy, e.g. LiteLLM)      | Enterprise  | One provider config → tenant's gateway URL         |
| #61 | SOC 2 / ISO 27001 evidence collection automation                                               | Enterprise  | Daily snapshots of access logs, config, etc.       |

---

## Stretch / research

These are exploratory and not committed to any stage yet.

| #     | Idea                                                                                                  |
|-------|-------------------------------------------------------------------------------------------------------|
| #62 | Self-improving router: log per-language outcomes → propose policy changes → admin approves           |
| #63 | "Coding agent benchmark" mode: run the same issue across N model policies, score by tests-pass rate  |
| #64 | Learned cost predictor (per-repo model that improves token-spend estimates over time)                |
| #65 | Local Llama-based "review" agent that runs *after* the cloud agent and gates merges                  |
| #66 | VS Code / JetBrains plugins that drive Ouroboros runs from inside the IDE                            |

---

## Seeding the issues

When this repo lands on GitHub, run:

```bash
bash scripts/seed_issues.sh OWNER/REPO
```

The script reads this file, opens one GitHub issue per `TBD-XX` row, applies
the right labels (`tier:mvp` / `tier:post-mvp` / `tier:cloud` /
`tier:enterprise` / `tier:research`), and rewrites this document in-place to
replace each `TBD-XX` placeholder with the real `#NN` issue number it created.
