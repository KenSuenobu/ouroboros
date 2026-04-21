"use client";

import { Flex, Text } from "@radix-ui/themes";
import type { ReactNode } from "react";

interface Props {
  sidebar: ReactNode;
  children: ReactNode;
}

export function PageShell({ sidebar, children }: Props) {
  return (
    <>
      <aside className="app-sidebar">{sidebar}</aside>
      <main className="app-main">{children}</main>
    </>
  );
}

interface HeaderProps {
  title: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
}

export function PageHeader({ title, subtitle, actions }: HeaderProps) {
  return (
    <Flex
      align="start"
      justify="between"
      gap="4"
      mb="5"
      style={{ paddingBottom: "var(--ob-space-4)", borderBottom: "1px solid var(--ob-border)" }}
    >
      <Flex direction="column" gap="1" style={{ minWidth: 0 }}>
        <Text
          as="div"
          weight="bold"
          style={{ fontSize: 22, letterSpacing: "-0.01em", color: "var(--ob-text-1)" }}
        >
          {title}
        </Text>
        {subtitle ? (
          <Text size="2" style={{ color: "var(--ob-text-2)" }}>
            {subtitle}
          </Text>
        ) : null}
      </Flex>
      {actions ? <Flex gap="2" style={{ flexShrink: 0 }}>{actions}</Flex> : null}
    </Flex>
  );
}
