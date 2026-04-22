"use client";

const BASE = "";

const PUBLIC_AUTH_PATHS = new Set<string>([
  "/login",
  "/setup",
]);

function isOnAuthPage(): boolean {
  if (typeof window === "undefined") return false;
  return PUBLIC_AUTH_PATHS.has(window.location.pathname);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    credentials: "include",
    cache: "no-store",
  });
  if (res.status === 401 && typeof window !== "undefined" && !isOnAuthPage()) {
    const next = encodeURIComponent(window.location.pathname + window.location.search);
    window.location.href = `/login?next=${next}`;
    throw new Error("401: not authenticated");
  }
  if (!res.ok) {
    let detail = res.statusText;
    const contentType = res.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      try {
        const body = await res.json();
        detail = body.detail || JSON.stringify(body);
      } catch {
        const raw = await res.text();
        if (raw.trim()) detail = raw.trim();
      }
    } else {
      const raw = await res.text();
      if (raw.trim()) detail = raw.trim();
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T,>(path: string) => request<T>(path),
  post: <T,>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  put: <T,>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body: body ? JSON.stringify(body) : undefined }),
  patch: <T,>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
  del: <T,>(path: string) => request<T>(path, { method: "DELETE" }),
};
