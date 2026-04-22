import type { NextConfig } from "next";
import packageJson from "./package.json";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  typedRoutes: false,
  env: {
    NEXT_PUBLIC_APP_VERSION: packageJson.version,
  },
  async rewrites() {
    // `/api/*` is served by the cookie-driven route handler in
    // `app/api/[...path]/route.ts`, which forwards to the user-selected
    // server. WebSocket connections still use the local rewrite below,
    // since route handlers can't proxy WebSocket frames; the front-end
    // WebSocket hook switches to absolute URLs when a remote server is
    // active.
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    return [
      { source: "/ws/:path*", destination: `${apiBase}/ws/:path*` },
    ];
  },
};

export default nextConfig;
