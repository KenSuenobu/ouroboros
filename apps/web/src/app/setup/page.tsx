"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { mutate } from "swr";
import { Button, Card, Flex, Heading, Text, TextField } from "@radix-ui/themes";
import { Infinity as InfinityIcon } from "lucide-react";
import { api } from "@/lib/api/client";
import { useAuthStatus } from "@/lib/auth/use-current-user";
import type { CurrentUser } from "@/lib/api/types";
import { ServerPicker } from "@/components/auth/server-picker";

export default function SetupPage() {
  const router = useRouter();
  const { data: status, isLoading: statusLoading, mutate: refreshStatus } = useAuthStatus();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (status && !status.needs_setup) {
      router.replace("/login");
    }
  }, [router, status]);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError("Password must be at least 8 characters long.");
      return;
    }
    setBusy(true);
    try {
      await api.post<CurrentUser>("/api/auth/setup", {
        email,
        password,
        display_name: displayName || null,
      });
      await mutate("/api/auth/status");
      await mutate("/api/auth/me");
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message.replace(/^\d+:\s*/, "") : "Setup failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main style={{ display: "grid", placeItems: "center", minHeight: "100dvh", padding: 24 }}>
      <Card size="4" style={{ width: "100%", maxWidth: 460 }}>
        <Flex direction="column" gap="4">
          <Flex align="center" gap="2">
            <InfinityIcon size={22} />
            <Heading size="5">Create the first administrator</Heading>
          </Flex>
          <Text size="2" color="gray">
            This account becomes the workspace administrator. You can invite more users from the
            admin console once you&apos;re signed in.
          </Text>

          <ServerPicker onChange={() => refreshStatus()} />

          {statusLoading ? (
            <Text size="2" color="gray">
              Checking status…
            </Text>
          ) : (
            <form onSubmit={onSubmit}>
              <Flex direction="column" gap="3">
                <label>
                  <Text as="div" size="2" mb="1" weight="medium">
                    Display name
                  </Text>
                  <TextField.Root
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    placeholder="Ada Lovelace"
                  />
                </label>
                <label>
                  <Text as="div" size="2" mb="1" weight="medium">
                    Email
                  </Text>
                  <TextField.Root
                    type="email"
                    autoComplete="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </label>
                <label>
                  <Text as="div" size="2" mb="1" weight="medium">
                    Password
                  </Text>
                  <TextField.Root
                    type="password"
                    autoComplete="new-password"
                    required
                    minLength={8}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                  <Text size="1" color="gray">
                    At least 8 characters.
                  </Text>
                </label>
                {error && (
                  <Text size="2" color="red">
                    {error}
                  </Text>
                )}
                <Button type="submit" disabled={busy}>
                  {busy ? "Creating account…" : "Create administrator"}
                </Button>
              </Flex>
            </form>
          )}
        </Flex>
      </Card>
    </main>
  );
}
