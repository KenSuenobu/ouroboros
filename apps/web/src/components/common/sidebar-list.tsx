"use client";

import { Flex, Text } from "@radix-ui/themes";
import type { ReactNode } from "react";

interface Item {
  id: string;
  primary: string;
  secondary?: string;
  badge?: ReactNode;
}

interface Props {
  title?: string;
  items: Item[];
  activeId?: string | null;
  onSelect: (id: string) => void;
  onAdd?: () => void;
  emptyLabel?: string;
}

export function SidebarList({ title, items, activeId, onSelect, onAdd, emptyLabel }: Props) {
  return (
    <Flex direction="column" gap="2">
      {title || onAdd ? (
        <Flex align="center" justify="between" px="2">
          {title ? <Text size="2" weight="bold" color="gray">{title}</Text> : <span />}
          {onAdd ? (
            <button
              type="button"
              onClick={onAdd}
              style={{
                background: "transparent",
                border: "1px solid var(--gray-a6)",
                color: "var(--accent-11)",
                borderRadius: 6,
                padding: "2px 8px",
                cursor: "pointer",
                fontSize: 12,
              }}
            >
              + New
            </button>
          ) : null}
        </Flex>
      ) : null}
      {items.length === 0 ? (
        <Text size="2" color="gray" style={{ padding: 12 }}>
          {emptyLabel || "(empty)"}
        </Text>
      ) : (
        items.map((item) => {
          const active = item.id === activeId;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onSelect(item.id)}
              style={{
                textAlign: "left",
                background: active ? "var(--accent-a4)" : "transparent",
                color: active ? "var(--accent-12)" : "var(--gray-12)",
                border: "1px solid transparent",
                borderRadius: 8,
                padding: "8px 10px",
                cursor: "pointer",
                width: "100%",
              }}
            >
              <Flex direction="column" gap="1">
                <Flex align="center" justify="between">
                  <Text size="2" weight={active ? "bold" : "medium"}>
                    {item.primary}
                  </Text>
                  {item.badge}
                </Flex>
                {item.secondary ? (
                  <Text size="1" color="gray">{item.secondary}</Text>
                ) : null}
              </Flex>
            </button>
          );
        })
      )}
    </Flex>
  );
}
