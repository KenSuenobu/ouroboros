"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Flex, Text, Badge, IconButton } from "@radix-ui/themes";
import {
  FolderTree,
  ListTodo,
  Activity,
  Bot,
  Plug,
  Boxes,
  Workflow,
  Infinity as InfinityIcon,
  HeartPulse,
  Moon,
  Sun,
} from "lucide-react";
import { useThemePreference } from "@/components/theme/app-theme-provider";

const NAV: Array<{ href: string; label: string; Icon: typeof FolderTree }> = [
  { href: "/projects", label: "Projects", Icon: FolderTree },
  { href: "/issues", label: "Issues", Icon: ListTodo },
  { href: "/runs", label: "Runs", Icon: Activity },
  { href: "/agents", label: "Agents", Icon: Bot },
  { href: "/providers", label: "Providers", Icon: Plug },
  { href: "/health", label: "Health", Icon: HeartPulse },
  { href: "/mcp", label: "MCP", Icon: Boxes },
  { href: "/routing", label: "Routing", Icon: Workflow },
];

export function TopHeader() {
  const pathname = usePathname();
  const { appearance, toggleTheme } = useThemePreference();
  const nextModeLabel = appearance === "dark" ? "light" : "dark";

  return (
    <Flex
      align="center"
      justify="between"
      px="4"
      style={{ borderBottom: "1px solid var(--gray-a5)", height: 56 }}
    >
      <Flex align="center" gap="3">
        <InfinityIcon size={22} color="var(--accent-9)" />
        <Text size="4" weight="bold">Ouroboros</Text>
        <Badge size="1" color="gray" variant="soft">v0.1</Badge>
      </Flex>
      <Flex gap="1">
        {NAV.map(({ href, label, Icon }) => {
          const active = pathname?.startsWith(href);
          return (
            <Link key={href} href={href} style={{ textDecoration: "none" }}>
              <Flex
                align="center"
                gap="2"
                px="3"
                py="2"
                style={{
                  borderRadius: 8,
                  background: active ? "var(--accent-a4)" : "transparent",
                  color: active ? "var(--accent-12)" : "var(--gray-12)",
                  cursor: "pointer",
                  fontSize: 14,
                  fontWeight: active ? 600 : 500,
                }}
              >
                <Icon size={16} />
                <span>{label}</span>
              </Flex>
            </Link>
          );
        })}
      </Flex>
      <Flex align="center" gap="2">
        <IconButton
          aria-label={`Switch to ${nextModeLabel} mode`}
          title={`Switch to ${nextModeLabel} mode`}
          variant="soft"
          color="gray"
          onClick={toggleTheme}
        >
          {appearance === "dark" ? <Sun size={16} /> : <Moon size={16} />}
        </IconButton>
        <Badge color="gray" variant="soft">default workspace</Badge>
      </Flex>
    </Flex>
  );
}
