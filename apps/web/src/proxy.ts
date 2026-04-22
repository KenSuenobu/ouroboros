import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { resolveBackendBase } from "@/lib/servers/resolve";

const PUBLIC_PATHS = new Set(["/login", "/setup"]);
const COOKIE_NAME = "ob_session";

const STATIC_PREFIXES = [
  "/_next",
  "/favicon",
  "/api",
  "/ws",
  "/static",
  "/assets",
];

function isPublic(path: string): boolean {
  if (PUBLIC_PATHS.has(path)) return true;
  return false;
}

function isStaticOrApi(path: string): boolean {
  return STATIC_PREFIXES.some((prefix) => path === prefix || path.startsWith(`${prefix}/`));
}

async function fetchAuthStatus(request: NextRequest): Promise<{
  needs_setup: boolean;
} | null> {
  try {
    const base = resolveBackendBase(request);
    const res = await fetch(`${base}/api/auth/status`, {
      headers: { cookie: request.headers.get("cookie") || "" },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as { needs_setup: boolean };
  } catch {
    return null;
  }
}

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (isStaticOrApi(pathname)) {
    return NextResponse.next();
  }

  const status = await fetchAuthStatus(request);
  const needsSetup = status?.needs_setup === true;
  const sessionCookie = request.cookies.get(COOKIE_NAME)?.value;

  if (needsSetup) {
    if (pathname !== "/setup") {
      const url = request.nextUrl.clone();
      url.pathname = "/setup";
      url.search = "";
      return NextResponse.redirect(url);
    }
    return NextResponse.next();
  }

  if (pathname === "/setup") {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    return NextResponse.redirect(url);
  }

  if (!sessionCookie) {
    if (isPublic(pathname)) return NextResponse.next();
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.search = `?next=${encodeURIComponent(pathname + request.nextUrl.search)}`;
    return NextResponse.redirect(url);
  }

  if (pathname === "/login") {
    const next = request.nextUrl.searchParams.get("next") || "/";
    const url = request.nextUrl.clone();
    url.pathname = next.startsWith("/") ? next : "/";
    url.search = "";
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|api|ws).*)",
  ],
};
