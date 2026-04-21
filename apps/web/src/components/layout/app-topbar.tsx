"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Moon, Search, Sun } from "lucide-react";
import { useThemePreference } from "@/components/theme/app-theme-provider";

const APP_VERSION = process.env.NEXT_PUBLIC_APP_VERSION || "dev";

const SECTION_LABEL: Record<string, string> = {
  projects: "Projects",
  issues: "Issues",
  runs: "Runs",
  agents: "Agents",
  providers: "Providers",
  health: "Health",
  mcp: "MCP",
  routing: "Routing",
};

type Crumb = { label: string; href?: string };

function pathToCrumbs(pathname: string): Crumb[] {
  const parts = pathname.split("/").filter(Boolean);
  if (parts.length === 0) return [{ label: "Projects" }];

  const crumbs: Crumb[] = [];
  const [section, ...rest] = parts;
  const sectionLabel = SECTION_LABEL[section] ?? section;
  crumbs.push(rest.length === 0 ? { label: sectionLabel } : { label: sectionLabel, href: `/${section}` });

  if (rest.length > 0) {
    const tail = rest[rest.length - 1];
    const display = tail.length > 14 ? `${tail.slice(0, 8)}…${tail.slice(-4)}` : tail;
    crumbs.push({ label: display });
  }

  return crumbs;
}

export function AppTopbar() {
  const pathname = usePathname() || "/";
  const { appearance, toggleTheme } = useThemePreference();
  const crumbs = pathToCrumbs(pathname);
  const nextModeLabel = appearance === "dark" ? "light" : "dark";

  return (
    <header className="ob-topbar">
      <nav className="ob-crumbs" aria-label="Breadcrumb">
        <span className="ob-workspace-pill" title="Current workspace">
          <span className="ob-workspace-dot" /> default
        </span>
        {crumbs.map((crumb, index) => {
          const isLast = index === crumbs.length - 1;
          return (
            <span key={`${crumb.label}-${index}`} style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
              <span className="ob-sep" aria-hidden="true">/</span>
              {isLast || !crumb.href ? (
                <strong>{crumb.label}</strong>
              ) : (
                <Link href={crumb.href}>{crumb.label}</Link>
              )}
            </span>
          );
        })}
      </nav>

      <div className="ob-topbar-actions">
        <button
          type="button"
          className="ob-search-trigger"
          aria-label="Open command palette"
          title="Command palette (coming in next phase)"
          disabled
        >
          <Search size={13} />
          <span className="ob-search-trigger-label">Search or jump to…</span>
          <span className="ob-kbd">⌘K</span>
        </button>
        <button
          type="button"
          className="ob-icon-btn"
          aria-label={`Switch to ${nextModeLabel} mode`}
          title={`Switch to ${nextModeLabel} mode`}
          onClick={toggleTheme}
        >
          {appearance === "dark" ? <Sun size={15} /> : <Moon size={15} />}
        </button>
        <span className="ob-workspace-pill" title="App version">v{APP_VERSION}</span>
      </div>
    </header>
  );
}
