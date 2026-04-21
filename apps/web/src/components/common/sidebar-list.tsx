"use client";

import { Flex, Text, TextField } from "@radix-ui/themes";
import type { ReactNode } from "react";
import { useMemo, useState } from "react";

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
  searchable?: boolean;
  searchPlaceholder?: string;
  emptySearchLabel?: string;
}

export function SidebarList({
  title,
  items,
  activeId,
  onSelect,
  onAdd,
  emptyLabel,
  searchable = false,
  searchPlaceholder = "Search",
  emptySearchLabel = "No matches",
}: Props) {
  const [query, setQuery] = useState("");
  const normalizedQuery = query.trim().toLowerCase();
  const filteredItems = useMemo(() => {
    if (!normalizedQuery) return items;
    return items.filter((item) => {
      const primary = item.primary.toLowerCase();
      const secondary = item.secondary?.toLowerCase() ?? "";
      return primary.includes(normalizedQuery) || secondary.includes(normalizedQuery);
    });
  }, [items, normalizedQuery]);

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
      {searchable ? (
        <TextField.Root
          size="1"
          placeholder={searchPlaceholder}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      ) : null}
      {filteredItems.length === 0 ? (
        <Text size="2" color="gray" style={{ padding: 12 }}>
          {normalizedQuery ? emptySearchLabel : emptyLabel || "(empty)"}
        </Text>
      ) : (
        filteredItems.map((item) => {
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
