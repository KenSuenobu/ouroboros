# Ouroboros — Business Model

> Ouroboros is an open-core agentic orchestrator. The local product is free and
> self-contained; the hosted product layers multi-tenant infra, billing, audit,
> and managed providers on top of the same engine. This document describes how
> we plan to make money without strangling the open core.

---

## 1. Product positioning

Ouroboros is a **bring-your-own-model agent orchestrator** for software
engineering. Every run takes an issue (or roadmap entry) and walks it through a
graph of agents until a PR is opened. Three things make it commercially
defensible:

1. **Provider-agnostic routing.** Ollama, Anthropic, GitHub Models, OpenCode,
   GitHub Copilot CLI, and any future LLM are first-class. Customers stop
   re-platforming every time a new model wins on a benchmark.
2. **Dry-run-by-default with promote.** Every run can be visualized and
   audited *before* anything touches the repo. This is the differentiator vs.
   Devin / Cursor Background / Codex Cloud, which apply changes optimistically.
3. **Designable flows.** The Routing page lets ops teams encode their own SDLC
   (linting gates, security review, change control, "must wait for human in
   prod branches", etc.) without forking the codebase.

Target customers, in escalating order:

| Persona                | Pain                                            | Wedge                       |
|------------------------|-------------------------------------------------|-----------------------------|
| Indie dev              | Spending $$$ on Cursor + Copilot + Claude       | Local Free, Ollama routing  |
| Small startup (5-25)   | Inconsistent agentic workflows per dev          | Cloud Solo / Cloud Team     |
| Scale-up (25-250)      | Compliance, audit, SSO, model governance        | Cloud Team                  |
| Enterprise (250+)      | On-prem / VPC, RBAC, retention, data locality   | Enterprise                  |

---

## 2. Tier ladder

### Local Free (open source, MIT)

* Full engine, all adapters, MCP support, designer, dry-run, audit log.
* SQLite, OS keyring, single workspace.
* No telemetry by default. Optional anonymized usage opt-in.

**Why give this away?** Distribution. Every Local Free user is a free QA
engineer for the engine, and a hot lead for Cloud once they need to share runs
with a teammate.

### Cloud Solo — $19 / month

* Hosted instance, persistent runs, GitHub OAuth login.
* Bring your own provider keys; we never charge per-token markup at this tier.
* 100 GB run artifact retention, 30-day event history.
* Email-only support.

### Cloud Team — $49 / user / month (min 3 seats)

* Multi-user workspace with RBAC (owner / maintainer / runner / viewer).
* Shared providers (admin sets the keys; users can't extract).
* Org-wide flow library, agent templates, MCP registry mirror.
* Audit log export (S3 / GCS), webhook delivery of `run.*` events.
* SLA: 99.5% uptime, 24h response.

### Cloud Team — Metered Models add-on (optional)

* Customers who *don't* want to manage provider keys can buy bundled inference.
* We resell Anthropic / OpenAI / Bedrock / Together / GitHub Models at a
  transparent markup (see §3) and put a hard monthly spend cap per workspace.
* Activated by toggling "Use Ouroboros-managed models" in Provider settings.

### Enterprise — custom

* Single-tenant deployment (k8s helm chart) in the customer's VPC, *or*
  dedicated hosted region with VPC peering.
* SAML/OIDC SSO, SCIM provisioning, IP allow lists, customer-managed KMS,
  customer-managed Secrets backend.
* Air-gapped / no-egress mode (Ollama-only routing enforced).
* 99.9% SLA, named CSM, security review pack (SOC 2, GDPR, DPA).
* Annual contract; floor ~$50k/yr, scales by seat count + run-minute pool.

---

## 3. Metering formula (Cloud)

Every run produces a metered `RunMeter` record:

```
billable_units = α · run_minutes
              + β · tokens_in / 1_000_000
              + γ · tokens_out / 1_000_000
              + δ · artifact_gb_stored
              + ε · concurrent_run_slot_hours
```

* **`α` (run minutes)** captures CPU / orchestration cost and prevents pure
  caching abuse.
* **`β` / `γ` (token volumes)** apply only when **Metered Models** is enabled.
  Charged at provider list price × **1.20** by default. The 20% markup covers
  payment processing, free-tier headroom, and supplier risk.
* **`δ` (artifact storage)** at $0.04 / GB-month for runs older than the
  free retention window.
* **`ε` (concurrency)** smooths burst usage. First 2 concurrent runs free; each
  additional concurrent slot is $5 / month.

The engine already collects `tokens_in`, `tokens_out`, and `cost_estimate_usd`
per `RunStep`, plus `total_*` on `Run`. The `RunMeter` table will be:

```
run_meters(
  id PK,
  workspace_id,
  run_id,
  provider_kind,        -- ollama / anthropic / github_models / ...
  model_id,
  source,               -- 'managed' | 'byok'
  tokens_in,
  tokens_out,
  cost_provider_usd,    -- our cost
  cost_billed_usd,      -- what the customer pays (0 for byok)
  measured_at
)
```

`cost_billed_usd` is the only thing we report to Stripe. Everything else is
diagnostic.

### Why a token markup at all (vs. flat seat pricing)?

Pure seat pricing is what Cursor / Copilot do, and it forces them to throttle
power users. We explicitly *do not* throttle: we want Ouroboros to be the tool
people reach for the second they have a non-trivial issue. Metered tokens align
revenue with value delivered.

### Why not 100% pass-through?

Three reasons: (a) provider invoices arrive at month-end with credit risk we
absorb; (b) we maintain redundant capacity across providers (model routing
failover); (c) Stripe and FX fees average ~3-5% before we touch margin.

---

## 4. Stripe wiring (cloud only)

* `stripe.Customer` per Workspace.
* `stripe.Subscription` for the per-seat base (Cloud Solo / Team).
* `stripe.SubscriptionItem` with `usage_type=metered` per metered dimension:
  * `seats` (license)
  * `tokens_in_managed`
  * `tokens_out_managed`
  * `artifact_gb`
  * `concurrent_slots`
* Engine pushes `usage_record` POSTs at run completion (and a final reconcile
  job nightly) — never per-step, to avoid Stripe rate limits.
* Webhooks back into FastAPI for `customer.subscription.deleted` →
  workspace gets a 14-day grace, then is downgraded to Local Free read-only
  (data retained 90 days).

The wiring touch-points in code:

```
apps/api/ouroboros_api/billing/stripe_client.py    # Stripe SDK wrapper
apps/api/ouroboros_api/billing/meter.py            # RunMeter aggregator
apps/api/ouroboros_api/billing/webhooks.py         # Stripe webhook router
apps/api/ouroboros_api/orchestrator/engine.py      # finalize_run() -> meter.record()
apps/web/src/app/billing/page.tsx                  # plan / usage UI
```

These files do **not** exist in the open-core repo; they live in a sibling
private package (`ouroboros-cloud`) loaded via entry points so the OSS code
stays untouchable.

---

## 5. Open-core boundary

| Lives in OSS (`ouroboros`)                | Lives in private (`ouroboros-cloud`)        |
|-------------------------------------------|---------------------------------------------|
| Engine, adapters, agents, MCP manager     | Stripe billing, RunMeter aggregator         |
| Routing designer, dry-run, audit log      | Policy-based RBAC, SSO/SAML/OIDC, SCIM      |
| Email + GitHub OAuth login, admin/member  | Per-team RBAC tiers, group-mapped roles     |
| roles per workspace, session mgmt         | enforcement                                 |
| All providers (Ollama, Anthropic, ...)    | Managed-models provider proxy + caching     |
| SQLite + Postgres backend                 | Multi-tenant migration tooling, vault       |
| `SecretsBackend` interface + `keyring`    | `VaultBackend`, `AwsKmsBackend` impls       |
| CLI (`ouroboros login`, `agent`, ...)     | Customer admin CLI, audit export            |

**The rule of thumb:** if it's needed to make a self-hosted instance *useful*,
it's open. If it's needed to *bill* or to *run a multi-tenant SaaS safely*, it's
private. We will not gate features behind a license check in the OSS codebase.

---

## 6. Moat analysis

The agent space is crowded. Our defensibility comes from:

1. **Provider-portability as a product surface.** Cursor, Devin, and Copilot
   bury model choice. We expose it, route on it, and let teams set
   per-language policy. As OSS proliferation continues (Llama 3.x, Qwen,
   DeepSeek), our value goes up while integrated competitors' goes down.

2. **Auditability.** Every run is a graph of typed events. Enterprises will
   pay for "show me which model wrote which line on which day." Most agentic
   tools today literally cannot answer this question.

3. **Dry-run + promote.** Most agent tools either commit optimistically
   (Cursor Background Agents, Codex Cloud) or never persist (Aider, Cline).
   Splitting plan-and-review from execute lets us sell into change-controlled
   shops (banks, gov, regulated SaaS) where agentic tools are otherwise banned.

4. **Flow designer as workflow lock-in.** Once a customer has 30 named flows
   encoding their lint policy, security gates, and PR template enforcement,
   the switching cost is no longer "rewrite a prompt" — it's "rewrite our
   SDLC." Salesforce taught us how powerful this is.

5. **MCP-native.** We're betting that MCP becomes the npm of agent tools. By
   shipping registry browse + per-step server spawning out of the box, we
   become the default place to *consume* MCP servers — which, like every
   marketplace, is the side that captures value.

The risks (also worth naming honestly):

* **Frontier-lab vertical integration.** Anthropic / OpenAI ship their own
  agent runtimes (Claude Code, ChatGPT Code Interpreter). Our defense:
  multi-provider routing means we win every time *any* customer wants to mix
  vendors, hedge against pricing changes, or run on Ollama.
* **VC-funded Cursor-likes commoditize on UI.** Our defense: the OSS engine
  becomes the substrate even competitors run on top of, à la VS Code → Cursor.
* **Compliance moat is slow.** SOC 2 takes 9-12 months. We start the
  Type I in month 6, target Type II by month 18, and sell to ICP pre-cert
  with bridge letters.

---

## 7. Headcount & milestones (rough)

| Stage                   | When     | Team           | What ships                       |
|-------------------------|----------|----------------|----------------------------------|
| OSS launch              | M0       | 2 eng          | Local Free (this repo)           |
| Cloud Solo waitlist     | M2       | 3 eng          | Hosted, GitHub OAuth, byok       |
| Cloud Team GA           | M5       | 4 eng + 1 GTM  | RBAC, shared providers, audit    |
| Managed Models add-on   | M7       | 5 eng + 1 GTM  | Stripe metering, provider proxy  |
| Enterprise design partn | M9       | 6 eng + 2 GTM  | Helm chart, SSO, KMS             |
| SOC 2 Type I            | M12      | 7 eng + 2 GTM  | Compliance pack                  |
| GA Enterprise           | M15      | 9 eng + 3 GTM  | Air-gapped + SCIM                |

---

## 8. What we will *not* do

* No "free tier with degraded models." The OSS version is the real version.
* No vendor lock to a single LLM. Even if we become preferred partners with
  Anthropic, GitHub, etc., the engine ships every adapter on equal footing.
* No prompt-stealing. We do not log prompts or completions in the cloud unless
  the workspace owner explicitly enables `audit_capture_prompts=true`.
* No "AI insights" upsell that mines customer code. If we ever ship a learning
  system, it runs per-tenant with explicit opt-in and per-run cohort data.

This document is a living spec. Update it whenever pricing, packaging, or the
open-core boundary changes.
