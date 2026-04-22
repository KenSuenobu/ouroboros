"use client";

import useSWR from "swr";
import { api } from "@/lib/api/client";
import type { AuthStatus, CurrentUser } from "@/lib/api/types";

const fetcher = <T,>(path: string) => api.get<T>(path);

export function useAuthStatus() {
  return useSWR<AuthStatus>("/api/auth/status", fetcher, {
    revalidateOnFocus: false,
  });
}

export function useCurrentUser() {
  return useSWR<CurrentUser>("/api/auth/me", fetcher, {
    revalidateOnFocus: false,
    shouldRetryOnError: false,
  });
}

export function isAdminInActiveWorkspace(
  user: CurrentUser | null | undefined,
  slug: string = "default",
): boolean {
  if (!user) return false;
  return user.memberships.some((m) => m.workspace_slug === slug && m.role === "admin");
}
