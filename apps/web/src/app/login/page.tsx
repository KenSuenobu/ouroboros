"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { mutate } from "swr";
import { Button, Card, Flex, Heading, Text, TextField } from "@radix-ui/themes";
import { Github, Infinity as InfinityIcon } from "lucide-react";
import { api } from "@/lib/api/client";
import { useAuthStatus } from "@/lib/auth/use-current-user";
import type { CurrentUser } from "@/lib/api/types";
import { ServerPicker } from "@/components/auth/server-picker";

export default function LoginPage() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params?.get("next") || "/";
  const { data: status, mutate: refreshStatus } = useAuthStatus();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (status?.needs_setup) {
      router.replace("/setup");
    }
  }, [router, status?.needs_setup]);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await api.post<CurrentUser>("/api/auth/login", { email, password });
      await mutate("/api/auth/me");
      router.replace(next.startsWith("/") ? next : "/");
    } catch (err) {
      setError(err instanceof Error ? err.message.replace(/^\d+:\s*/, "") : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main style={{ display: "grid", placeItems: "center", minHeight: "100dvh", padding: 24 }}>
      <Card size="4" style={{ width: "100%", maxWidth: 400 }}>
        <Flex direction="column" gap="4">
          <Flex align="center" gap="2">
            <InfinityIcon size={22} />
            <Heading size="5">Sign in to Ouroboros</Heading>
          </Flex>
          <ServerPicker
            onChange={() => {
              refreshStatus();
              mutate("/api/auth/me", undefined, { revalidate: false });
            }}
          />

          <form onSubmit={onSubmit}>
            <Flex direction="column" gap="3">
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
                  placeholder="you@example.com"
                />
              </label>
              <label>
                <Text as="div" size="2" mb="1" weight="medium">
                  Password
                </Text>
                <TextField.Root
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </label>
              {error && (
                <Text size="2" color="red">
                  {error}
                </Text>
              )}
              <Button type="submit" disabled={busy}>
                {busy ? "Signing in…" : "Sign in"}
              </Button>
            </Flex>
          </form>

          {status?.github_oauth_enabled && (
            <Flex direction="column" gap="2">
              <div
                style={{
                  height: 1,
                  background: "var(--gray-a5)",
                  margin: "4px 0",
                }}
              />
              <Button asChild variant="soft" color="gray">
                <a href="/api/auth/oauth/github/start">
                  <Github size={16} />
                  Sign in with GitHub
                </a>
              </Button>
            </Flex>
          )}

          {status?.open_registration && (
            <Text size="1" color="gray" align="center">
              Need an account?{" "}
              <Link href="/setup">Register</Link>
            </Text>
          )}
        </Flex>
      </Card>
    </main>
  );
}
