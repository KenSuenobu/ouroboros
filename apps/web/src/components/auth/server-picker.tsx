"use client";

import { useEffect, useState } from "react";
import {
  Box,
  Button,
  Dialog,
  Flex,
  Select,
  Text,
  TextField,
} from "@radix-ui/themes";
import { Plus, Server as ServerIcon, Trash } from "lucide-react";
import {
  addServer,
  ensureActiveServerCookie,
  getActiveServerId,
  listServers,
  removeServer,
  setActiveServer,
  type ServerEntry,
} from "@/lib/servers/registry";

type Props = {
  /** Called whenever the active server changes. */
  onChange?: (server: ServerEntry) => void;
};

export function ServerPicker({ onChange }: Props) {
  const [servers, setServers] = useState<ServerEntry[]>([]);
  const [activeId, setActiveId] = useState<string>("local");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [label, setLabel] = useState("");
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);

  function refresh() {
    setServers(listServers());
    setActiveId(getActiveServerId());
  }

  useEffect(() => {
    refresh();
    ensureActiveServerCookie();
  }, []);

  function selectServer(id: string) {
    if (id === "__add__") {
      setDialogOpen(true);
      return;
    }
    const entry = setActiveServer(id);
    setActiveId(entry.id);
    onChange?.(entry);
  }

  function onAdd(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    try {
      const entry = addServer(label, url);
      setActiveServer(entry.id);
      setLabel("");
      setUrl("");
      setDialogOpen(false);
      refresh();
      onChange?.(entry);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add server.");
    }
  }

  function onRemove(id: string) {
    removeServer(id);
    refresh();
  }

  const active = servers.find((s) => s.id === activeId);

  return (
    <Box>
      <Text as="div" size="2" weight="medium" mb="1">
        <Flex align="center" gap="2">
          <ServerIcon size={14} />
          Server
        </Flex>
      </Text>
      <Select.Root value={activeId} onValueChange={selectServer}>
        <Select.Trigger style={{ width: "100%" }} />
        <Select.Content>
          {servers.map((s) => (
            <Select.Item key={s.id} value={s.id}>
              {s.label}
              {!s.builtin ? (
                <Text as="span" size="1" color="gray" ml="2">
                  {s.url}
                </Text>
              ) : (
                <Text as="span" size="1" color="gray" ml="2">
                  this device
                </Text>
              )}
            </Select.Item>
          ))}
          <Select.Separator />
          <Select.Item value="__add__">
            <Flex align="center" gap="2">
              <Plus size={12} /> Add a remote server…
            </Flex>
          </Select.Item>
        </Select.Content>
      </Select.Root>
      {active && !active.builtin && (
        <Flex justify="between" align="center" mt="1">
          <Text size="1" color="gray">{active.url}</Text>
          <Button
            size="1"
            variant="ghost"
            color="red"
            onClick={() => onRemove(active.id)}
          >
            <Trash size={12} /> Remove
          </Button>
        </Flex>
      )}

      <Dialog.Root open={dialogOpen} onOpenChange={setDialogOpen}>
        <Dialog.Content maxWidth="420px">
          <Dialog.Title>Add a remote Ouroboros server</Dialog.Title>
          <Dialog.Description size="2" mb="3">
            Connect to a server hosted elsewhere. The browser will route every
            API call through this machine to the chosen server.
          </Dialog.Description>
          <form onSubmit={onAdd}>
            <Flex direction="column" gap="3">
              <label>
                <Text as="div" size="2" mb="1" weight="medium">Label</Text>
                <TextField.Root
                  required
                  value={label}
                  onChange={(e) => setLabel(e.target.value)}
                  placeholder="Production"
                />
              </label>
              <label>
                <Text as="div" size="2" mb="1" weight="medium">Base URL</Text>
                <TextField.Root
                  required
                  type="url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://ouroboros.example.com"
                />
                <Text size="1" color="gray">
                  Include scheme and host. Do not include `/api`.
                </Text>
              </label>
              {error && <Text size="2" color="red">{error}</Text>}
              <Flex gap="2" justify="end">
                <Dialog.Close>
                  <Button type="button" variant="soft">Cancel</Button>
                </Dialog.Close>
                <Button type="submit">Add and use</Button>
              </Flex>
            </Flex>
          </form>
        </Dialog.Content>
      </Dialog.Root>
    </Box>
  );
}
