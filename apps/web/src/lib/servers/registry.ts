"use client";

/**
 * Multi-server support for the web client.
 *
 * The browser always talks to its own origin under `/api/*`. A Next route
 * handler at `/api/[...path]` reads the `ob_server` cookie and proxies the
 * request to the user-selected backend, so session cookies stay first-party
 * regardless of where the API lives.
 *
 * The local server is a built-in entry that maps to the dev/baked default
 * (`NEXT_PUBLIC_API_URL` or `http://localhost:8000`). User-added remote
 * servers are persisted to localStorage and reflected in a non-`HttpOnly`
 * cookie so the proxy route can read it without an extra round-trip.
 */

const STORAGE_KEY = "ob_servers_v1";
const ACTIVE_KEY = "ob_active_server_v1";
export const SERVER_COOKIE = "ob_server";
const COOKIE_MAX_AGE_DAYS = 365;

export const LOCAL_SERVER_ID = "local";

export type ServerEntry = {
  id: string;
  label: string;
  url: string;
  builtin?: boolean;
};

const LOCAL_SERVER: ServerEntry = {
  id: LOCAL_SERVER_ID,
  label: "Local",
  url: "local",
  builtin: true,
};

function isBrowser(): boolean {
  return typeof window !== "undefined";
}

function readCustomServers(): ServerEntry[] {
  if (!isBrowser()) return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as ServerEntry[];
    return Array.isArray(parsed)
      ? parsed.filter((s) => s && typeof s.url === "string" && s.id !== LOCAL_SERVER_ID)
      : [];
  } catch {
    return [];
  }
}

function writeCustomServers(servers: ServerEntry[]): void {
  if (!isBrowser()) return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(servers));
}

function setCookie(name: string, value: string, days: number): void {
  if (!isBrowser()) return;
  const maxAge = days * 24 * 60 * 60;
  document.cookie = `${name}=${encodeURIComponent(value)}; Path=/; Max-Age=${maxAge}; SameSite=Lax`;
}

function deleteCookie(name: string): void {
  if (!isBrowser()) return;
  document.cookie = `${name}=; Path=/; Max-Age=0; SameSite=Lax`;
}

function readCookie(name: string): string | null {
  if (!isBrowser()) return null;
  const match = document.cookie.match(new RegExp(`(?:^|;\\s*)${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

export function listServers(): ServerEntry[] {
  return [LOCAL_SERVER, ...readCustomServers()];
}

export function normalizeServerUrl(input: string): string {
  const trimmed = input.trim().replace(/\/+$/, "");
  if (!trimmed) throw new Error("Server URL is required.");
  if (trimmed === "local") return "local";
  if (!/^https?:\/\//i.test(trimmed)) {
    throw new Error("Server URL must start with http:// or https://");
  }
  try {
    new URL(trimmed);
  } catch {
    throw new Error("Server URL is not a valid URL.");
  }
  return trimmed;
}

export function addServer(label: string, url: string): ServerEntry {
  const cleanedUrl = normalizeServerUrl(url);
  const cleanedLabel = label.trim() || cleanedUrl;
  const id = `srv_${Math.random().toString(36).slice(2, 10)}`;
  const entry: ServerEntry = { id, label: cleanedLabel, url: cleanedUrl };
  const all = readCustomServers();
  if (all.some((s) => s.url === cleanedUrl)) {
    const existing = all.find((s) => s.url === cleanedUrl)!;
    return existing;
  }
  writeCustomServers([...all, entry]);
  return entry;
}

export function removeServer(id: string): void {
  if (id === LOCAL_SERVER_ID) return;
  const all = readCustomServers().filter((s) => s.id !== id);
  writeCustomServers(all);
  if (getActiveServerId() === id) {
    setActiveServer(LOCAL_SERVER_ID);
  }
}

export function getActiveServerId(): string {
  if (!isBrowser()) return LOCAL_SERVER_ID;
  return window.localStorage.getItem(ACTIVE_KEY) || LOCAL_SERVER_ID;
}

export function getActiveServer(): ServerEntry {
  const id = getActiveServerId();
  return listServers().find((s) => s.id === id) || LOCAL_SERVER;
}

/**
 * Switch the active server. We mirror the choice into a cookie so the
 * `/api/[...path]` route handler (which runs server-side per request) can
 * forward to the right backend without needing to inspect localStorage.
 */
export function setActiveServer(id: string): ServerEntry {
  const entry = listServers().find((s) => s.id === id) || LOCAL_SERVER;
  if (isBrowser()) {
    window.localStorage.setItem(ACTIVE_KEY, entry.id);
    setCookie(SERVER_COOKIE, entry.url, COOKIE_MAX_AGE_DAYS);
  }
  return entry;
}

export function ensureActiveServerCookie(): void {
  if (!isBrowser()) return;
  const cookie = readCookie(SERVER_COOKIE);
  const active = getActiveServer();
  if (cookie !== active.url) {
    setCookie(SERVER_COOKIE, active.url, COOKIE_MAX_AGE_DAYS);
  }
}

export function clearActiveServer(): void {
  if (!isBrowser()) return;
  window.localStorage.removeItem(ACTIVE_KEY);
  deleteCookie(SERVER_COOKIE);
}
