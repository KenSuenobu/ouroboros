"use client";

import { useState } from "react";
import Link from "next/link";
import { Button, Card, Flex, Heading, Text, TextField } from "@radix-ui/themes";
import { ChevronLeft } from "lucide-react";
import { api } from "@/lib/api/client";
import { useCurrentUser } from "@/lib/auth/use-current-user";
import { RequireAuth } from "@/lib/auth/guards";

function PasswordCard() {
  const { data: user } = useCurrentUser();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setDone(false);
    if (next !== confirm) {
      setError("New passwords do not match.");
      return;
    }
    if (next.length < 8) {
      setError("Password must be at least 8 characters long.");
      return;
    }
    setBusy(true);
    try {
      await api.post("/api/auth/password", {
        current_password: user?.has_password ? current : null,
        new_password: next,
      });
      setCurrent("");
      setNext("");
      setConfirm("");
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message.replace(/^\d+:\s*/, "") : "Failed to change password.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card size="3">
      <Flex direction="column" gap="3">
        <Heading size="3">Password</Heading>
        <form onSubmit={onSubmit}>
          <Flex direction="column" gap="3">
            {user?.has_password && (
              <label>
                <Text as="div" size="2" mb="1" weight="medium">Current password</Text>
                <TextField.Root
                  type="password"
                  required
                  value={current}
                  onChange={(e) => setCurrent(e.target.value)}
                />
              </label>
            )}
            <label>
              <Text as="div" size="2" mb="1" weight="medium">New password</Text>
              <TextField.Root
                type="password"
                required
                minLength={8}
                value={next}
                onChange={(e) => setNext(e.target.value)}
              />
              <Text size="1" color="gray">At least 8 characters. All other sessions will be signed out.</Text>
            </label>
            <label>
              <Text as="div" size="2" mb="1" weight="medium">Confirm new password</Text>
              <TextField.Root
                type="password"
                required
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
              />
            </label>
            {error && <Text size="2" color="red">{error}</Text>}
            {done && <Text size="2" color="green">Password updated.</Text>}
            <Button type="submit" disabled={busy} style={{ alignSelf: "flex-start" }}>
              {busy ? "Saving…" : "Update password"}
            </Button>
          </Flex>
        </form>
      </Flex>
    </Card>
  );
}

function ProfileCard() {
  const { data: user } = useCurrentUser();
  if (!user) return null;
  return (
    <Card size="3">
      <Flex direction="column" gap="2">
        <Heading size="3">Profile</Heading>
        <Flex direction="column" gap="1">
          <Text size="1" color="gray">Display name</Text>
          <Text size="3">{user.display_name || "(not set)"}</Text>
        </Flex>
        <Flex direction="column" gap="1">
          <Text size="1" color="gray">Email</Text>
          <Text size="3">{user.email}</Text>
        </Flex>
        {user.linked_oauth.length > 0 && (
          <Flex direction="column" gap="1">
            <Text size="1" color="gray">Linked accounts</Text>
            <Text size="3">{user.linked_oauth.join(", ")}</Text>
          </Flex>
        )}
        <Flex direction="column" gap="1">
          <Text size="1" color="gray">Workspaces</Text>
          {user.memberships.map((m) => (
            <Text key={m.workspace_id} size="2">
              {m.workspace_name} <Text as="span" size="1" color="gray">({m.role})</Text>
            </Text>
          ))}
        </Flex>
      </Flex>
    </Card>
  );
}

export default function AccountPage() {
  return (
    <RequireAuth>
      <div style={{ maxWidth: 720, margin: "0 auto", padding: "var(--ob-space-6)" }}>
        <Flex align="center" gap="2" mb="4">
          <Link href="/" style={{ display: "inline-flex", alignItems: "center", color: "var(--ob-text-2)" }}>
            <ChevronLeft size={16} /> Back
          </Link>
          <Heading size="5" ml="2">Account</Heading>
        </Flex>
        <Flex direction="column" gap="4">
          <ProfileCard />
          <PasswordCard />
        </Flex>
      </div>
    </RequireAuth>
  );
}
