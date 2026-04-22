"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Bot,
  Boxes,
  FolderTree,
  HeartPulse,
  Infinity as InfinityIcon,
  ListTodo,
  Plug,
  Settings,
  Workflow,
} from "lucide-react";
import type { ComponentType } from "react";
import { isAdminInActiveWorkspace, useCurrentUser } from "@/lib/auth/use-current-user";

type NavItem = {
  href: string;
  label: string;
  Icon: ComponentType<{ size?: number }>;
  adminOnly?: boolean;
};

const NAV: NavItem[] = [
  { href: "/projects", label: "Projects", Icon: FolderTree },
  { href: "/issues", label: "Issues", Icon: ListTodo },
  { href: "/runs", label: "Runs", Icon: Activity },
  { href: "/agents", label: "Agents", Icon: Bot, adminOnly: true },
  { href: "/providers", label: "Providers", Icon: Plug, adminOnly: true },
  { href: "/health", label: "Health", Icon: HeartPulse },
  { href: "/mcp", label: "MCP", Icon: Boxes, adminOnly: true },
  { href: "/routing", label: "Routing", Icon: Workflow, adminOnly: true },
];

export function AppRail() {
  const pathname = usePathname() || "";
  const { data: user } = useCurrentUser();
  const isAdmin = isAdminInActiveWorkspace(user);
  const visible = NAV.filter((item) => !item.adminOnly || isAdmin);

  return (
    <aside className="ob-rail" aria-label="Primary navigation">
      <Link href="/projects" className="ob-rail-logo" aria-label="Ouroboros home">
        <InfinityIcon size={18} />
      </Link>
      {visible.map(({ href, label, Icon }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            className="ob-rail-btn"
            data-active={active}
            aria-label={label}
            aria-current={active ? "page" : undefined}
          >
            <Icon size={18} />
            <span className="ob-rail-tip" role="tooltip">{label}</span>
          </Link>
        );
      })}
      <div className="ob-rail-spacer" />
      <div className="ob-rail-divider" />
      <button type="button" className="ob-rail-btn" aria-label="Settings (coming soon)" disabled>
        <Settings size={18} />
        <span className="ob-rail-tip" role="tooltip">Settings</span>
      </button>
    </aside>
  );
}
