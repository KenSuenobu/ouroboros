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

---

## Stage 1 — MVP correctness & onboarding

| #     | Issue                                                                                          | Tier | Notes                                                    |
|-------|------------------------------------------------------------------------------------------------|------|----------------------------------------------------------|
| TBD-01 | First-run onboarding wizard (workspace name → first project → first provider key)              | MVP  | Wraps the `/projects`, `/providers` flows in a guided 3-step modal |
| TBD-02 | Healthcheck panel: ping each configured provider, surface "needs key" / "ollama unreachable"   | MVP  | New `GET /api/providers/{id}/health` and a `/health` page       |
| TBD-03 | Auto-detect repo `build`/`test` commands (package.json scripts, pyproject sections, Makefile)  | MVP  | Pre-fills Project commands so first run "just works"             |
| TBD-04 | Improved router default policy (per-language) baked into seed agents, not just `coder`         | MVP  | Currently only the `coder` agent has language hints              |
| TBD-05 | Real-time stderr/stdout streaming for shell steps (not just final blob)                        | MVP  | New `step.log` events on the WebSocket bus                       |
| TBD-06 | Persisted `.env` for `OUROBOROS_DB_URL` etc. via `ouroboros init` CLI                          | MVP  | Today envs are read but never written for the user               |
| TBD-07 | "Resume" button when a run was interrupted by a crash mid-step                                 | MVP  | Engine has `attempts` but no resume from prior step              |
| TBD-08 | Robust dry-run diff viewer: real side-by-side using Monaco's `DiffEditor`                      | MVP  | Current `DiffViewer` is a thin wrapper; needs left/right inputs  |

## Stage 2 — UX & power-user features

| #     | Issue                                                                                          | Tier      | Notes                                                |
|-------|------------------------------------------------------------------------------------------------|-----------|------------------------------------------------------|
| TBD-09 | Side-by-side run comparison view (pick two runs → diff their plans, costs, artifacts)         | Post-MVP  | Useful for A/B testing two model policies            |
| TBD-10 | Cost forecast on the "Run this issue" button (estimate tokens before clicking)                 | Post-MVP  | Uses average per-step token counts from history      |
| TBD-11 | Saved router presets ("frontend stack", "data eng stack") shared across agents                 | Post-MVP  | Currently router hints are per-agent JSON            |
| TBD-12 | Inline issue triage: rewrite acceptance criteria from the UI before kicking off the run        | Post-MVP  | Editable issue body that flows into the planner      |
| TBD-13 | Multi-issue batch runs (queue 5 issues, watch them progress in parallel with global cap)       | Post-MVP  | Engine already supports concurrent runs              |
| TBD-14 | Notification adapters: webhook, Slack, email, Linear comment when a run finishes               | Post-MVP  | New `NotificationAdapter` ABC                        |
| TBD-15 | Project-level "do not auto-merge" / "require human approval" rule on the flow graph            | Post-MVP  | Adds a `require_approval` node type                  |
| TBD-16 | Diff-aware planner: Planner gets a structured repo summary (file tree + recent commits)        | Post-MVP  | Reduces token cost vs. dumping the whole repo        |
| TBD-17 | Sandbox snapshotting: copy-on-write `git worktree`-backed sandbox per run                      | Post-MVP  | Faster than full re-clone for big repos              |
| TBD-18 | Local artifact storage GC (LRU eviction beyond N GB)                                            | Post-MVP  | Prevents `data/runs/` from filling disk              |
| TBD-19 | Provider failover: if Anthropic 5xx mid-run, retry on a routed Ollama equivalent               | Post-MVP  | Engine retry hook exists; provider routing does not  |
| TBD-20 | First-class GitLab support parity (issue body markdown render, MR comments, pipelines)         | Post-MVP  | Today GitLab is functional but UI-light              |
| TBD-21 | First-class Bitbucket Cloud + Bitbucket DC adapter                                              | Post-MVP  | Needed for many regulated shops                      |
| TBD-22 | Roadmap-aware planner: pull the matched roadmap entry into the planner system prompt           | Post-MVP  | We already produce pairs; we don't yet consume them  |
| TBD-23 | Inline MCP tool inspector (right pane in Run detail showing each tool call as it happens)      | Post-MVP  | Useful for debugging long agent loops                |
| TBD-24 | "Replay" mode: re-run a failed step against a different model without restarting the whole run | Post-MVP  | Hot-swap model on a single step                      |
| TBD-25 | Convert any successful run into a reusable Flow template ("save as flow")                      | Post-MVP  | Closes the design loop: run → flow → run             |

## Stage 3 — Quality, observability, and operability

| #     | Issue                                                                                          | Tier      | Notes                                                |
|-------|------------------------------------------------------------------------------------------------|-----------|------------------------------------------------------|
| TBD-26 | Structured JSON event log → file rotation in `data/logs/` with `structlog` JSON renderer       | Post-MVP  | Today we log to stderr only                          |
| TBD-27 | Prometheus `/metrics` endpoint (run rates, token spend, intervention age, MCP failure rate)    | Post-MVP  | Hosted instances need this                           |
| TBD-28 | OpenTelemetry tracing for each agent step (provider, model, latency, tokens) → OTLP exporter   | Post-MVP  | Instrument the engine + adapters                     |
| TBD-29 | Backup / restore CLI (`ouroboros backup`, `ouroboros restore`)                                 | Post-MVP  | SQLite + `data/runs/` tarball                        |
| TBD-30 | Migration story: SQLite → Postgres single command                                              | Post-MVP  | First step toward Cloud Solo                         |
| TBD-31 | Fuzz tests for `classify_command` (random shell commands → expected category)                  | Post-MVP  | Hardens the dry-run guarantee                        |
| TBD-32 | Adversarial test pack: prompt-injection issues that try to escape the sandbox                  | Post-MVP  | Run weekly in CI                                     |
| TBD-33 | Provider rate-limit-aware backpressure (Anthropic 429 → exponential pause)                     | Post-MVP  | Avoids burning a session on rate limits              |
| TBD-34 | Configurable model price catalog (load `provider_prices.yaml` so cost stays current)           | Post-MVP  | Today prices are inferred from provider API only     |

## Stage 4 — Cloud (Solo / Team)

| #     | Issue                                                                                          | Tier      | Notes                                                |
|-------|------------------------------------------------------------------------------------------------|-----------|------------------------------------------------------|
| TBD-35 | Auth: GitHub OAuth + email magic link login                                                    | Cloud     | Lives in private `ouroboros-cloud` package           |
| TBD-36 | Workspace invites + role assignment (owner / maintainer / runner / viewer)                     | Cloud     | RBAC enforcement on every router                    |
| TBD-37 | Org-shared providers (admin sets key, members consume; key never returned to client)           | Cloud     | Reuses `SecretsBackend(VaultBackend)`                |
| TBD-38 | Stripe metered billing wiring (`RunMeter` aggregator + nightly reconcile job)                  | Cloud     | Detailed in `BUSINESS_MODEL.md` §4                   |
| TBD-39 | Managed Models proxy: outbound reseller for Anthropic / OpenAI / Bedrock with caching          | Cloud     | Optional add-on, gated per workspace                 |
| TBD-40 | S3-compatible artifact storage backend (`ArtifactStore` ABC)                                   | Cloud     | Today artifacts live on local disk                   |
| TBD-41 | Audit log export (S3 / GCS / webhook) with daily delivery                                      | Cloud     | Compliance-grade tamper-evident log                  |
| TBD-42 | Webhook delivery for `run.*` events with HMAC signing + retry                                  | Cloud     | Replaces in-process bus for external listeners       |
| TBD-43 | Public REST API tokens (separate from session) with per-token rate limiting                    | Cloud     | Programmatic CI integrations                         |

## Stage 5 — Enterprise

| #     | Issue                                                                                          | Tier        | Notes                                              |
|-------|------------------------------------------------------------------------------------------------|-------------|----------------------------------------------------|
| TBD-44 | SAML / OIDC SSO with JIT provisioning                                                          | Enterprise  | Required to cross the $50k/yr line                 |
| TBD-45 | SCIM 2.0 user / group provisioning                                                             | Enterprise  | Sync from Okta / Azure AD                          |
| TBD-46 | Customer-managed KMS for `SecretsBackend` (BYOK)                                               | Enterprise  | AWS KMS, GCP KMS, HashiCorp Vault                  |
| TBD-47 | Air-gapped deploy mode (Ollama-only routing enforced; no outbound calls from agents)           | Enterprise  | Hard-fails if any adapter would dial the internet  |
| TBD-48 | Policy engine: OPA/Rego rules per workspace (e.g. "never run on `prod/*` branches")            | Enterprise  | Evaluated at flow start + before each side-effect  |
| TBD-49 | Data residency selector (workspace pinned to a region; data never leaves)                      | Enterprise  | Required for EU / APAC                             |
| TBD-50 | Customer-managed CA + mTLS between API ↔ web ↔ MCP servers                                     | Enterprise  | For regulated networks                             |
| TBD-51 | Tamper-evident append-only audit log (Merkle-chained event log; daily root signed and shipped) | Enterprise  | SOX-friendly                                       |
| TBD-52 | Long-form retention policies per data class (artifacts 90d, audit 7y, prompts 0d)              | Enterprise  | Configurable, per-tenant                           |
| TBD-53 | Helm chart + Terraform module for self-hosted deployment                                       | Enterprise  | Targets EKS, GKE, AKS, OpenShift                   |
| TBD-54 | Customer-managed model gateway (terminate at customer's existing LLM proxy, e.g. LiteLLM)      | Enterprise  | One provider config → tenant's gateway URL         |
| TBD-55 | SOC 2 / ISO 27001 evidence collection automation                                               | Enterprise  | Daily snapshots of access logs, config, etc.       |

---

## Stretch / research

These are exploratory and not committed to any stage yet.

| #     | Idea                                                                                                  |
|-------|-------------------------------------------------------------------------------------------------------|
| TBD-56 | Self-improving router: log per-language outcomes → propose policy changes → admin approves           |
| TBD-57 | "Coding agent benchmark" mode: run the same issue across N model policies, score by tests-pass rate  |
| TBD-58 | Learned cost predictor (per-repo model that improves token-spend estimates over time)                |
| TBD-59 | Local Llama-based "review" agent that runs *after* the cloud agent and gates merges                  |
| TBD-60 | VS Code / JetBrains plugins that drive Ouroboros runs from inside the IDE                            |

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
