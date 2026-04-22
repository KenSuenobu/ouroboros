/**
 * Server-side helper used by the `/api/[...path]` and `/ws/[...path]` route
 * handlers to resolve the actual backend URL for a given request.
 *
 * The browser stores the chosen backend in the `ob_server` cookie. The value
 * is either:
 *   - the literal string `"local"`, meaning "use the local API base"
 *   - or an absolute URL like `https://api.acme.example`.
 *
 * The local API base is taken from `NEXT_PUBLIC_API_URL` (falling back to
 * `http://localhost:8000`) so dev, prod, and self-hosted deployments all
 * route correctly without the user having to register their own server.
 */

import type { NextRequest } from "next/server";

export const SERVER_COOKIE = "ob_server";
const LOCAL_FALLBACK = "http://localhost:8000";

export function localApiBase(): string {
  return (process.env.NEXT_PUBLIC_API_URL || LOCAL_FALLBACK).replace(/\/+$/, "");
}

function isAbsoluteHttpUrl(value: string): boolean {
  return /^https?:\/\//i.test(value);
}

export function resolveBackendBase(request: NextRequest): string {
  const cookie = request.cookies.get(SERVER_COOKIE)?.value;
  if (!cookie || cookie === "local") {
    return localApiBase();
  }
  if (!isAbsoluteHttpUrl(cookie)) {
    return localApiBase();
  }
  return cookie.replace(/\/+$/, "");
}
