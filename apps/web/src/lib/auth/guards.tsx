"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import type { ReactNode } from "react";
import { useCurrentUser, isAdminInActiveWorkspace } from "./use-current-user";

export function RequireAuth({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { data, error, isLoading } = useCurrentUser();

  useEffect(() => {
    if (error) {
      const next = encodeURIComponent(window.location.pathname + window.location.search);
      router.replace(`/login?next=${next}`);
    }
  }, [error, router]);

  if (isLoading) {
    return null;
  }
  if (!data) {
    return null;
  }
  return <>{children}</>;
}

export function RequireAdmin({ children, fallback = null }: { children: ReactNode; fallback?: ReactNode }) {
  const { data } = useCurrentUser();
  if (!data) return null;
  if (!isAdminInActiveWorkspace(data)) return <>{fallback}</>;
  return <>{children}</>;
}
