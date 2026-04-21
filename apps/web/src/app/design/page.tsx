"use client";

import "./preview.css";
import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  Bot,
  Boxes,
  Check,
  Clipboard,
  Command as CommandIcon,
  ExternalLink,
  FolderTree,
  HeartPulse,
  Infinity as InfinityIcon,
  ListTodo,
  Plug,
  Search,
  Settings,
  Sparkles,
  Workflow,
  X,
} from "lucide-react";

type Section = "projects" | "runs";

const NAV: Array<{ id: Section | string; label: string; Icon: typeof FolderTree }> = [
  { id: "projects", label: "Projects", Icon: FolderTree },
  { id: "issues", label: "Issues", Icon: ListTodo },
  { id: "runs", label: "Runs", Icon: Activity },
  { id: "agents", label: "Agents", Icon: Bot },
  { id: "providers", label: "Providers", Icon: Plug },
  { id: "health", label: "Health", Icon: HeartPulse },
  { id: "mcp", label: "MCP", Icon: Boxes },
  { id: "routing", label: "Routing", Icon: Workflow },
];

const PROJECTS = [
  { id: "p1", name: "ouroboros-cli", repo: "github.com/acme/ouroboros-cli", branch: "main", token: true },
  { id: "p2", name: "billing-service", repo: "github.com/acme/billing", branch: "trunk", token: true },
  { id: "p3", name: "marketing-site", repo: "github.com/acme/site", branch: "main", token: false },
  { id: "p4", name: "internal-tools", repo: "gitlab.com/acme/tools", branch: "main", token: true },
];

const RUNS = [
  { id: "r1", title: "Refactor auth middleware", status: "succeeded", issue: 412, tokensIn: 18420, tokensOut: 4210, cost: 0.0421, when: "2m ago" },
  { id: "r2", title: "Add idempotency keys to /charge", status: "running", issue: 418, tokensIn: 9210, tokensOut: 1820, cost: 0.0184, when: "running" },
  { id: "r3", title: "Audit unused feature flags", status: "interrupted", issue: 401, tokensIn: 4221, tokensOut: 880, cost: 0.0093, when: "12m ago" },
  { id: "r4", title: "dry-run · upgrade Next 16", status: "failed", issue: 422, tokensIn: 2120, tokensOut: 220, cost: 0.0028, when: "31m ago", dry: true },
  { id: "r5", title: "Generate changelog 0.2.0", status: "succeeded", issue: null, tokensIn: 1422, tokensOut: 318, cost: 0.0017, when: "1h ago" },
];

export default function DesignPreviewPage() {
  const [section, setSection] = useState<Section>("projects");
  const [activeProject, setActiveProject] = useState("p1");
  const [tab, setTab] = useState<"overview" | "settings" | "issues" | "runs">("settings");
  const [paletteOpen, setPaletteOpen] = useState(false);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen((open) => !open);
      }
      if (event.key === "Escape") setPaletteOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="dx">
      <Rail section={section} onSection={(value) => setSection(value as Section)} />

      {section === "projects" ? (
        <ProjectsList activeId={activeProject} onSelect={setActiveProject} />
      ) : (
        <RunsList />
      )}

      <main className="dx-main">
        <Topbar section={section} onOpenPalette={() => setPaletteOpen(true)} project={section === "projects" ? PROJECTS.find((p) => p.id === activeProject)?.name : null} tab={tab} />
        {section === "projects" ? (
          <>
            <Tabs value={tab} onChange={setTab} />
            <div className="dx-content">
              <div className="dx-content-inner">
                {tab === "settings" ? <ProjectSettings /> : <ComingSoon label={tab} />}
              </div>
            </div>
          </>
        ) : (
          <div className="dx-content">
            <div className="dx-content-inner">
              <RunsTable />
            </div>
          </div>
        )}
      </main>

      {paletteOpen ? <CommandPalette onClose={() => setPaletteOpen(false)} onJump={(s) => { setSection(s); setPaletteOpen(false); }} /> : null}

      <DesignBanner onOpenPalette={() => setPaletteOpen(true)} />
    </div>
  );
}

/* ---------------- Rail ---------------- */

function Rail({ section, onSection }: { section: string; onSection: (id: string) => void }) {
  return (
    <aside className="dx-rail">
      <div className="dx-rail-logo" title="Ouroboros">
        <InfinityIcon size={18} />
      </div>
      {NAV.map(({ id, label, Icon }) => (
        <button
          key={id}
          type="button"
          className="dx-rail-btn"
          data-active={section === id}
          onClick={() => onSection(id)}
          aria-label={label}
        >
          <Icon size={18} />
          <span className="dx-rail-tip">{label}</span>
        </button>
      ))}
      <div className="dx-rail-spacer" />
      <div className="dx-rail-divider" />
      <button type="button" className="dx-rail-btn" aria-label="Settings">
        <Settings size={18} />
        <span className="dx-rail-tip">Settings</span>
      </button>
    </aside>
  );
}

/* ---------------- Projects list ---------------- */

function ProjectsList({ activeId, onSelect }: { activeId: string; onSelect: (id: string) => void }) {
  const [query, setQuery] = useState("");
  const filtered = useMemo(
    () => PROJECTS.filter((project) => `${project.name} ${project.repo}`.toLowerCase().includes(query.toLowerCase())),
    [query],
  );
  return (
    <aside className="dx-list">
      <div className="dx-list-header">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span className="dx-list-title">Projects · {PROJECTS.length}</span>
          <button type="button" className="dx-btn dx-btn--sm dx-btn--ghost" title="New project">+ New</button>
        </div>
        <label className="dx-search">
          <Search size={13} />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Filter projects" />
          <span className="dx-kbd">/</span>
        </label>
      </div>
      <div className="dx-list-scroll">
        {filtered.map((project) => (
          <button
            key={project.id}
            type="button"
            className="dx-list-item"
            data-active={activeId === project.id}
            onClick={() => onSelect(project.id)}
          >
            <div className="dx-list-item-row">
              <span className="dx-list-item-name">{project.name}</span>
              {project.token ? (
                <span className="dx-pill dx-pill--ok" title="Access token configured">
                  <span className="dx-pill-dot" /> auth
                </span>
              ) : (
                <span className="dx-pill dx-pill--warn" title="No access token">
                  <span className="dx-pill-dot" /> public
                </span>
              )}
            </div>
            <span className="dx-list-item-sub">{project.repo}</span>
          </button>
        ))}
      </div>
    </aside>
  );
}

/* ---------------- Runs list (left column for runs section) ---------------- */

function RunsList() {
  const [query, setQuery] = useState("");
  const items = ["All projects", ...PROJECTS.map((p) => p.name)];
  const filtered = items.filter((item) => item.toLowerCase().includes(query.toLowerCase()));
  return (
    <aside className="dx-list">
      <div className="dx-list-header">
        <span className="dx-list-title">Filter by project</span>
        <label className="dx-search">
          <Search size={13} />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Filter projects" />
        </label>
      </div>
      <div className="dx-list-scroll">
        {filtered.map((item, index) => (
          <button key={item} type="button" className="dx-list-item" data-active={index === 0}>
            <span className="dx-list-item-name">{item}</span>
          </button>
        ))}
      </div>
    </aside>
  );
}

/* ---------------- Topbar / breadcrumbs ---------------- */

function Topbar({
  section,
  project,
  tab,
  onOpenPalette,
}: {
  section: string;
  project?: string | null;
  tab?: string;
  onOpenPalette: () => void;
}) {
  return (
    <div className="dx-topbar">
      <div className="dx-crumbs">
        <a href="#">acme</a>
        <span className="dx-sep">/</span>
        <a href="#" style={{ textTransform: "capitalize" }}>{section}</a>
        {project ? (
          <>
            <span className="dx-sep">/</span>
            <a href="#">{project}</a>
            {tab ? (
              <>
                <span className="dx-sep">/</span>
                <strong style={{ textTransform: "capitalize" }}>{tab}</strong>
              </>
            ) : null}
          </>
        ) : null}
      </div>
      <div className="dx-topbar-actions">
        <button type="button" className="dx-btn dx-btn--ghost" onClick={onOpenPalette}>
          <Search size={14} />
          <span style={{ color: "var(--dx-text-3)" }}>Search or jump to…</span>
          <span className="dx-kbd" style={{ marginLeft: 8 }}>⌘K</span>
        </button>
        <button type="button" className="dx-icon-btn" aria-label="Notifications">
          <Sparkles size={15} />
        </button>
        <div style={{ width: 28, height: 28, borderRadius: 999, background: "var(--accent-a5)", color: "var(--accent-12)", display: "grid", placeItems: "center", fontSize: 12, fontWeight: 600 }}>K</div>
      </div>
    </div>
  );
}

function Tabs({ value, onChange }: { value: string; onChange: (v: "overview" | "settings" | "issues" | "runs") => void }) {
  const tabs: Array<{ id: "overview" | "settings" | "issues" | "runs"; label: string }> = [
    { id: "overview", label: "Overview" },
    { id: "issues", label: "Issues" },
    { id: "runs", label: "Runs" },
    { id: "settings", label: "Settings" },
  ];
  return (
    <div className="dx-tabs">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          className="dx-tab"
          data-active={value === tab.id}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

/* ---------------- Project settings (the form rethink) ---------------- */

function ProjectSettings() {
  const [testStatus, setTestStatus] = useState<"idle" | "ok" | "err">("idle");
  return (
    <>
      <header className="dx-page-head">
        <div>
          <div className="dx-page-title">ouroboros-cli</div>
          <div className="dx-page-sub">
            <span className="dx-code-row">
              <span className="dx-code">github.com/acme/ouroboros-cli</span>
              <button type="button" className="dx-icon-btn" aria-label="Copy"><Clipboard size={12} /></button>
              <a href="#" style={{ color: "var(--dx-text-2)", display: "inline-flex", alignItems: "center", gap: 4 }}>open <ExternalLink size={12} /></a>
            </span>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button type="button" className="dx-btn dx-btn--danger">Delete project</button>
          <button type="button" className="dx-btn dx-btn--primary">Save changes</button>
        </div>
      </header>

      <section className="dx-section">
        <header className="dx-section-head">
          <div>
            <div className="dx-section-title">Identity</div>
            <div className="dx-section-sub">How this project shows up across runs and dashboards.</div>
          </div>
        </header>
        <div className="dx-section-body">
          <Field label="Name">
            <input className="dx-input" defaultValue="ouroboros-cli" />
          </Field>
          <Field label="SCM">
            <select className="dx-select" defaultValue="github">
              <option value="github">GitHub</option>
              <option value="gitlab">GitLab</option>
            </select>
          </Field>
          <Field label="Default branch">
            <input className="dx-input dx-input--mono" defaultValue="main" />
          </Field>
          <Field label="Local clone hint" hint="Optional · used for roadmap parsing">
            <input className="dx-input dx-input--mono" placeholder="~/code/ouroboros-cli" />
          </Field>
        </div>
      </section>

      <section className="dx-section">
        <header className="dx-section-head">
          <div>
            <div className="dx-section-title">Repository access</div>
            <div className="dx-section-sub">Token is stored encrypted at rest.</div>
          </div>
          <span className="dx-pill dx-pill--ok"><span className="dx-pill-dot" /> token configured</span>
        </header>
        <div className="dx-section-body dx-section-body--single">
          <Field label="Repository URL">
            <div className="dx-input-row">
              <input className="dx-input dx-input--mono" defaultValue="https://github.com/acme/ouroboros-cli" />
              <button
                type="button"
                className={`dx-btn ${testStatus === "ok" ? "dx-btn--primary" : ""}`}
                onClick={() => setTestStatus(Math.random() > 0.3 ? "ok" : "err")}
              >
                {testStatus === "ok" ? <Check size={13} /> : null}
                Test access
              </button>
            </div>
            {testStatus !== "idle" ? (
              <div style={{ marginTop: 8 }}>
                {testStatus === "ok" ? (
                  <span className="dx-pill dx-pill--ok"><span className="dx-pill-dot" /> reachable · 247 commits · last push 4h ago</span>
                ) : (
                  <span className="dx-pill dx-pill--err"><span className="dx-pill-dot" /> 401 · token cannot read repo metadata</span>
                )}
              </div>
            ) : null}
          </Field>
          <Field label="Access token" hint="Leave blank to keep existing">
            <input className="dx-input dx-input--mono" type="password" placeholder="●●●●●●●●●●●●●●●●●●" />
            <div style={{ marginTop: 8, display: "flex", gap: 8 }}>
              <button type="button" className="dx-btn dx-btn--sm">Use GitHub OAuth</button>
              <button type="button" className="dx-btn dx-btn--sm dx-btn--ghost">Paste from 1Password</button>
            </div>
          </Field>
        </div>
      </section>

      <section className="dx-section">
        <header className="dx-section-head">
          <div>
            <div className="dx-section-title">Build & test</div>
            <div className="dx-section-sub">Detected from repo. Click a suggestion to use it.</div>
          </div>
        </header>
        <div className="dx-section-body">
          <Field label="Build command">
            <input className="dx-input dx-input--mono" defaultValue="npm run build" />
            <SuggestRow items={["pnpm build", "yarn build", "npm run build"]} />
          </Field>
          <Field label="Test command">
            <input className="dx-input dx-input--mono" defaultValue="npm test" />
            <SuggestRow items={["pnpm test", "vitest run", "jest --ci"]} />
          </Field>
        </div>
      </section>

      <details className="dx-section">
        <summary className="dx-section-head" style={{ cursor: "pointer", listStyle: "none" }}>
          <div>
            <div className="dx-section-title">Advanced configuration</div>
            <div className="dx-section-sub">Raw JSON. Override at your own risk.</div>
          </div>
          <span className="dx-pill"><span className="dx-pill-dot" /> 0 overrides</span>
        </summary>
        <div className="dx-section-body dx-section-body--single">
          <Field label="config.json">
            <textarea className="dx-textarea" rows={6} defaultValue={"{\n  \n}"} />
          </Field>
        </div>
      </details>
    </>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="dx-field">
      <div className="dx-field-label">
        <span>{label}</span>
        {hint ? <span className="dx-field-hint">{hint}</span> : null}
      </div>
      {children}
    </div>
  );
}

function SuggestRow({ items }: { items: string[] }) {
  return (
    <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
      <span className="dx-field-hint" style={{ alignSelf: "center" }}>suggested</span>
      {items.map((item) => (
        <button key={item} type="button" className="dx-btn dx-btn--sm dx-btn--ghost">
          <span className="dx-code">{item}</span>
        </button>
      ))}
    </div>
  );
}

/* ---------------- Runs table ---------------- */

function RunsTable() {
  return (
    <>
      <header className="dx-page-head">
        <div>
          <div className="dx-page-title">Runs</div>
          <div className="dx-page-sub">Each run is one orchestrated execution of a flow against an issue.</div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button type="button" className="dx-btn">Filter</button>
          <button type="button" className="dx-btn dx-btn--primary">Start run</button>
        </div>
      </header>

      <div className="dx-callout">
        <Sparkles size={15} className="dx-callout-icon" />
        <div>
          <strong style={{ fontWeight: 600 }}>Runs detail view inherits this density.</strong>{" "}
          The plan graph, log stream, and intervention prompts now sit in three resizable panes instead of stacked tabs.
        </div>
      </div>

      <div className="dx-runs">
        <div className="dx-run-head">
          <div>Title</div>
          <div>Status</div>
          <div style={{ textAlign: "right" }}>Tokens in / out</div>
          <div style={{ textAlign: "right" }}>Cost</div>
          <div style={{ textAlign: "right" }}>When</div>
        </div>
        {RUNS.map((run) => (
          <div key={run.id} className="dx-run-row">
            <div className="dx-run-title">
              <div className="dx-run-title-main">
                <strong>{run.title}</strong>
                {run.dry ? <span className="dx-pill dx-pill--warn"><span className="dx-pill-dot" /> dry</span> : null}
              </div>
              <span className="dx-run-title-sub">
                {run.id} {run.issue ? `· issue #${run.issue}` : ""}
              </span>
            </div>
            <StatusPill status={run.status} />
            <div className="dx-run-num">{run.tokensIn.toLocaleString()} / {run.tokensOut.toLocaleString()}</div>
            <div className="dx-run-num">${run.cost.toFixed(4)}</div>
            <div className="dx-run-num">{run.when}</div>
          </div>
        ))}
      </div>
    </>
  );
}

function StatusPill({ status }: { status: string }) {
  const map: Record<string, string> = {
    succeeded: "dx-pill--ok",
    running: "dx-pill--info",
    interrupted: "dx-pill--warn",
    failed: "dx-pill--err",
  };
  return (
    <span className={`dx-pill ${map[status] || ""}`}>
      <span className="dx-pill-dot" /> {status}
    </span>
  );
}

function ComingSoon({ label }: { label: string }) {
  return (
    <div className="dx-callout">
      <Sparkles size={15} className="dx-callout-icon" />
      <div><strong style={{ fontWeight: 600, textTransform: "capitalize" }}>{label}</strong> view in the new shell would render here. The existing page would slot in unchanged — only its container changes.</div>
    </div>
  );
}

/* ---------------- Command palette stub ---------------- */

function CommandPalette({ onClose, onJump }: { onClose: () => void; onJump: (id: Section) => void }) {
  const [query, setQuery] = useState("");
  const sections = [
    {
      label: "Pages",
      items: NAV.map(({ id, label, Icon }) => ({ id, label, Icon, hint: `g ${id.toString().charAt(0)}` })),
    },
    {
      label: "Projects",
      items: PROJECTS.map((p) => ({ id: p.id, label: p.name, Icon: FolderTree, hint: p.repo })),
    },
    {
      label: "Runs",
      items: RUNS.slice(0, 3).map((r) => ({ id: r.id, label: r.title, Icon: Activity, hint: r.id })),
    },
  ];
  const filter = (label: string) => label.toLowerCase().includes(query.toLowerCase());
  return (
    <div className="dx-cmdk-backdrop" onClick={onClose}>
      <div className="dx-cmdk" onClick={(e) => e.stopPropagation()}>
        <input
          autoFocus
          className="dx-cmdk-input"
          placeholder="Type a command, page, project, or run…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <div className="dx-cmdk-list">
          {sections.map((section) => {
            const items = section.items.filter((item) => filter(item.label));
            if (items.length === 0) return null;
            return (
              <div key={section.label}>
                <div className="dx-cmdk-section">{section.label}</div>
                {items.map((item, index) => {
                  const Icon = item.Icon;
                  const active = index === 0 && section.label === "Pages";
                  return (
                    <div
                      key={item.id}
                      className="dx-cmdk-item"
                      data-active={active}
                      onClick={() => {
                        if (section.label === "Pages") onJump(item.id as Section);
                        else onClose();
                      }}
                    >
                      <span className="dx-cmdk-item-icon"><Icon size={15} /></span>
                      <span className="dx-cmdk-item-name">{item.label}</span>
                      <span className="dx-cmdk-item-hint">{item.hint}</span>
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
        <div className="dx-cmdk-foot">
          <span><CommandIcon size={12} /> Powered by cmdk (mock)</span>
          <span><span className="dx-kbd">↵</span> open · <span className="dx-kbd">esc</span> close</span>
        </div>
      </div>
    </div>
  );
}

function DesignBanner({ onOpenPalette }: { onOpenPalette: () => void }) {
  return (
    <div className="dx-banner">
      <span>Design preview · not connected to live data.</span>
      <button type="button" className="dx-btn dx-btn--sm" onClick={onOpenPalette}>
        Try <span className="dx-kbd" style={{ marginLeft: 6 }}>⌘K</span>
      </button>
      <a href="/projects" aria-label="Exit preview" style={{ display: "inline-flex" }}>
        <X size={14} />
      </a>
    </div>
  );
}
