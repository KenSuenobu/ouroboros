"use client";

import { useState } from "react";
import Link from "next/link";
import useSWR, { mutate } from "swr";
import {
  Badge,
  Box,
  Button,
  Card,
  Dialog,
  Flex,
  Heading,
  IconButton,
  Select,
  Switch,
  Table,
  Text,
  TextField,
} from "@radix-ui/themes";
import { ChevronLeft, Plus, Trash } from "lucide-react";
import { api } from "@/lib/api/client";
import type { AdminUser } from "@/lib/api/types";
import { RequireAdmin, RequireAuth } from "@/lib/auth/guards";
import { useCurrentUser } from "@/lib/auth/use-current-user";

const USERS_KEY = "/api/users";
const fetcher = <T,>(path: string) => api.get<T>(path);

function CreateUserDialog({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"admin" | "member">("member");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function reset() {
    setEmail("");
    setDisplayName("");
    setPassword("");
    setRole("member");
    setError(null);
  }

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post(USERS_KEY, {
        email: email.trim(),
        display_name: displayName.trim() || null,
        password: password || null,
        role,
      });
      onCreated();
      setOpen(false);
      reset();
    } catch (err) {
      setError(err instanceof Error ? err.message.replace(/^\d+:\s*/, "") : "Failed to create user.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={(next) => { setOpen(next); if (!next) reset(); }}>
      <Dialog.Trigger>
        <Button>
          <Plus size={14} /> Add user
        </Button>
      </Dialog.Trigger>
      <Dialog.Content maxWidth="420px">
        <Dialog.Title>Add a user</Dialog.Title>
        <Dialog.Description size="2" mb="3">
          New users can log in with email and password. Leave the password blank to require GitHub OAuth.
        </Dialog.Description>
        <form onSubmit={onSubmit}>
          <Flex direction="column" gap="3">
            <label>
              <Text as="div" size="2" mb="1" weight="medium">Email</Text>
              <TextField.Root
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
            <label>
              <Text as="div" size="2" mb="1" weight="medium">Display name</Text>
              <TextField.Root
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
              />
            </label>
            <label>
              <Text as="div" size="2" mb="1" weight="medium">Initial password (optional)</Text>
              <TextField.Root
                type="password"
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <Text size="1" color="gray">At least 8 characters.</Text>
            </label>
            <label>
              <Text as="div" size="2" mb="1" weight="medium">Role</Text>
              <Select.Root value={role} onValueChange={(v) => setRole(v as "admin" | "member")}>
                <Select.Trigger />
                <Select.Content>
                  <Select.Item value="member">Member</Select.Item>
                  <Select.Item value="admin">Admin</Select.Item>
                </Select.Content>
              </Select.Root>
            </label>
            {error && <Text size="2" color="red">{error}</Text>}
            <Flex gap="2" justify="end">
              <Dialog.Close>
                <Button type="button" variant="soft">Cancel</Button>
              </Dialog.Close>
              <Button type="submit" disabled={busy}>{busy ? "Creating…" : "Create user"}</Button>
            </Flex>
          </Flex>
        </form>
      </Dialog.Content>
    </Dialog.Root>
  );
}

function UserRow({ user, isSelf }: { user: AdminUser; isSelf: boolean }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function update(patch: Record<string, unknown>) {
    setBusy(true);
    setError(null);
    try {
      await api.patch(`/api/users/${user.id}`, patch);
      await mutate(USERS_KEY);
    } catch (err) {
      setError(err instanceof Error ? err.message.replace(/^\d+:\s*/, "") : "Update failed.");
      setTimeout(() => setError(null), 4000);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!confirm(`Remove ${user.email} from this workspace?`)) return;
    setBusy(true);
    setError(null);
    try {
      await api.del(`/api/users/${user.id}`);
      await mutate(USERS_KEY);
    } catch (err) {
      setError(err instanceof Error ? err.message.replace(/^\d+:\s*/, "") : "Remove failed.");
      setTimeout(() => setError(null), 4000);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Table.Row>
      <Table.Cell>
        <Flex direction="column">
          <Text size="2" weight="medium">{user.display_name || user.email}</Text>
          <Text size="1" color="gray">{user.email}</Text>
          {error && <Text size="1" color="red">{error}</Text>}
        </Flex>
      </Table.Cell>
      <Table.Cell>
        <Select.Root
          value={user.role}
          onValueChange={(v) => update({ role: v })}
          disabled={busy || isSelf}
        >
          <Select.Trigger />
          <Select.Content>
            <Select.Item value="member">Member</Select.Item>
            <Select.Item value="admin">Admin</Select.Item>
          </Select.Content>
        </Select.Root>
      </Table.Cell>
      <Table.Cell>
        <Flex align="center" gap="2">
          <Switch
            checked={user.is_active}
            onCheckedChange={(checked) => update({ is_active: checked })}
            disabled={busy || isSelf}
          />
          <Text size="2" color={user.is_active ? undefined : "gray"}>
            {user.is_active ? "Active" : "Disabled"}
          </Text>
        </Flex>
      </Table.Cell>
      <Table.Cell>
        <Flex gap="1" wrap="wrap">
          {user.has_password && <Badge color="gray" variant="soft">Password</Badge>}
          {user.linked_oauth.map((p) => (
            <Badge key={p} color="iris" variant="soft">{p}</Badge>
          ))}
        </Flex>
      </Table.Cell>
      <Table.Cell>
        <Text size="1" color="gray">
          {user.last_login_at ? new Date(user.last_login_at).toLocaleString() : "Never"}
        </Text>
      </Table.Cell>
      <Table.Cell>
        <IconButton
          color="red"
          variant="ghost"
          onClick={remove}
          disabled={busy || isSelf}
          title={isSelf ? "You cannot remove yourself" : "Remove from workspace"}
        >
          <Trash size={14} />
        </IconButton>
      </Table.Cell>
    </Table.Row>
  );
}

function UsersTable() {
  const { data: users, error, isLoading } = useSWR<AdminUser[]>(USERS_KEY, fetcher);
  const { data: me } = useCurrentUser();

  if (isLoading) return <Text color="gray">Loading users…</Text>;
  if (error) return <Text color="red">{(error as Error).message}</Text>;
  if (!users || users.length === 0) return <Text color="gray">No users yet.</Text>;

  return (
    <Card size="2">
      <Table.Root>
        <Table.Header>
          <Table.Row>
            <Table.ColumnHeaderCell>User</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Role</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Status</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Sign-in</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Last login</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell aria-label="Actions" />
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {users.map((u) => (
            <UserRow key={u.id} user={u} isSelf={me?.id === u.id} />
          ))}
        </Table.Body>
      </Table.Root>
    </Card>
  );
}

function Page() {
  return (
    <div style={{ maxWidth: 960, margin: "0 auto", padding: "var(--ob-space-6)" }}>
      <Flex align="center" justify="between" mb="4">
        <Flex align="center" gap="2">
          <Link href="/" style={{ display: "inline-flex", alignItems: "center", color: "var(--ob-text-2)" }}>
            <ChevronLeft size={16} /> Back
          </Link>
          <Heading size="5" ml="2">Workspace users</Heading>
        </Flex>
        <CreateUserDialog onCreated={() => mutate(USERS_KEY)} />
      </Flex>
      <Box mb="3">
        <Text size="2" color="gray">
          Admins can manage providers, agents, flows, MCP servers, and other users. Members can run flows and intervene in runs.
        </Text>
      </Box>
      <UsersTable />
    </div>
  );
}

export default function AdminUsersPage() {
  return (
    <RequireAuth>
      <RequireAdmin
        fallback={
          <div style={{ maxWidth: 600, margin: "120px auto", textAlign: "center" }}>
            <Heading size="4" mb="2">Admins only</Heading>
            <Text size="2" color="gray">You need to be an admin in this workspace to manage users.</Text>
            <Box mt="3">
              <Link href="/">Go back</Link>
            </Box>
          </div>
        }
      >
        <Page />
      </RequireAdmin>
    </RequireAuth>
  );
}
