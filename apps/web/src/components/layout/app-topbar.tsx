"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LogOut, Moon, Search, Server as ServerIcon, Sun, User as UserIcon } from "lucide-react";
import { mutate } from "swr";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useThemePreference } from "@/components/theme/app-theme-provider";
import { api } from "@/lib/api/client";
import { isAdminInActiveWorkspace, useCurrentUser } from "@/lib/auth/use-current-user";
import {
  ensureActiveServerCookie,
  getActiveServer,
  LOCAL_SERVER_ID,
  listServers,
  setActiveServer,
  type ServerEntry,
} from "@/lib/servers/registry";

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

function initials(value: string): string {
  const cleaned = value.trim();
  if (!cleaned) return "?";
  const parts = cleaned.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return cleaned.slice(0, 2).toUpperCase();
}

export function AppTopbar() {
  const pathname = usePathname() || "/";
  const router = useRouter();
  const { appearance, toggleTheme } = useThemePreference();
  const crumbs = pathToCrumbs(pathname);
  const nextModeLabel = appearance === "dark" ? "light" : "dark";
  const { data: user } = useCurrentUser();
  const isAdmin = isAdminInActiveWorkspace(user);
  const [activeServer, setActiveServerState] = useState<ServerEntry | null>(null);
  const [servers, setServers] = useState<ServerEntry[]>([]);

  useEffect(() => {
    ensureActiveServerCookie();
    setActiveServerState(getActiveServer());
    setServers(listServers());
  }, []);

  function switchServer(id: string) {
    const next = setActiveServer(id);
    setActiveServerState(next);
    mutate("/api/auth/status");
    mutate("/api/auth/me", undefined, { revalidate: false });
    router.replace("/login");
  }

  async function signOut() {
    try {
      await api.post("/api/auth/logout");
    } catch {
      // ignore - we redirect regardless
    }
    await mutate("/api/auth/me", undefined, { revalidate: false });
    router.replace("/login");
  }

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
        {activeServer && servers.length > 0 && (
          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <button
                type="button"
                className="ob-workspace-pill ob-server-pill"
                aria-label="Switch server"
                title={
                  activeServer.id === LOCAL_SERVER_ID
                    ? "Connected to local server"
                    : `Connected to ${activeServer.url}`
                }
              >
                <ServerIcon size={12} />
                {activeServer.label}
              </button>
            </DropdownMenu.Trigger>
            <DropdownMenu.Portal>
              <DropdownMenu.Content className="ob-menu" sideOffset={6} align="end">
                <DropdownMenu.Label className="ob-menu-label">Server</DropdownMenu.Label>
                {servers.map((s) => (
                  <DropdownMenu.Item
                    key={s.id}
                    className="ob-menu-item"
                    data-active={s.id === activeServer.id || undefined}
                    onSelect={() => switchServer(s.id)}
                  >
                    <ServerIcon size={14} />
                    <span style={{ flex: 1 }}>{s.label}</span>
                    {s.id !== LOCAL_SERVER_ID && (
                      <span style={{ fontSize: 11, color: "var(--ob-text-3)" }}>
                        {s.url.replace(/^https?:\/\//, "")}
                      </span>
                    )}
                  </DropdownMenu.Item>
                ))}
                <DropdownMenu.Separator className="ob-menu-sep" />
                <DropdownMenu.Item asChild className="ob-menu-item">
                  <a href="/login">Add or manage servers…</a>
                </DropdownMenu.Item>
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
        )}
        <span className="ob-workspace-pill" title="App version">v{APP_VERSION}</span>
        {user && (
          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <button
                type="button"
                className="ob-user-trigger"
                aria-label="Account menu"
                title={user.email}
              >
                <span className="ob-avatar" aria-hidden="true">{initials(user.display_name || user.email)}</span>
                <span className="ob-user-meta">
                  <span className="ob-user-name">{user.display_name || user.email}</span>
                  <span className="ob-role-badge" data-role={isAdmin ? "admin" : "member"}>
                    {isAdmin ? "Admin" : "Member"}
                  </span>
                </span>
              </button>
            </DropdownMenu.Trigger>
            <DropdownMenu.Portal>
              <DropdownMenu.Content className="ob-menu" sideOffset={6} align="end">
                <DropdownMenu.Label className="ob-menu-label">{user.email}</DropdownMenu.Label>
                <DropdownMenu.Item asChild>
                  <Link href="/account" className="ob-menu-item">
                    <UserIcon size={14} /> Account
                  </Link>
                </DropdownMenu.Item>
                {isAdmin && (
                  <DropdownMenu.Item asChild>
                    <Link href="/admin/users" className="ob-menu-item">
                      <UserIcon size={14} /> Manage users
                    </Link>
                  </DropdownMenu.Item>
                )}
                <DropdownMenu.Separator className="ob-menu-sep" />
                <DropdownMenu.Item className="ob-menu-item" onSelect={signOut}>
                  <LogOut size={14} /> Sign out
                </DropdownMenu.Item>
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
        )}
      </div>
    </header>
  );
}
