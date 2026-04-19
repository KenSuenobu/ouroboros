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
  subtitle?: string;
  actions?: ReactNode;
}

export function PageHeader({ title, subtitle, actions }: HeaderProps) {
  return (
    <Flex align="start" justify="between" mb="4">
      <Flex direction="column" gap="1">
        <Text size="6" weight="bold">{title}</Text>
        {subtitle ? <Text size="2" color="gray">{subtitle}</Text> : null}
      </Flex>
      {actions ? <Flex gap="2">{actions}</Flex> : null}
    </Flex>
  );
}
