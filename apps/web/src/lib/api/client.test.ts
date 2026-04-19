import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { api } from "./client";

declare global {
  // eslint-disable-next-line no-var
  var fetch: typeof window.fetch;
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      if (url === "/api/projects" && (!init || init.method === undefined)) {
        return new Response(JSON.stringify([{ id: "p1" }]), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      if (url === "/api/projects" && init?.method === "POST") {
        return new Response(JSON.stringify({ id: "p2" }), {
          status: 201,
          headers: { "content-type": "application/json" },
        });
      }
      if (url === "/api/boom") {
        return new Response(JSON.stringify({ detail: "kaboom" }), {
          status: 500,
          headers: { "content-type": "application/json" },
        });
      }
      if (url === "/api/empty") {
        return new Response(null, { status: 204 });
      }
      return new Response("not found", { status: 404 });
    }) as typeof fetch,
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api client", () => {
  it("performs a GET and returns JSON", async () => {
    const result = await api.get<Array<{ id: string }>>("/api/projects");
    expect(result).toEqual([{ id: "p1" }]);
  });

  it("performs a POST with JSON body", async () => {
    const result = await api.post<{ id: string }>("/api/projects", { name: "x" });
    expect(result).toEqual({ id: "p2" });
  });

  it("throws with detail on non-2xx", async () => {
    await expect(api.get("/api/boom")).rejects.toThrow(/kaboom/);
  });

  it("returns undefined on 204", async () => {
    const result = await api.del("/api/empty");
    expect(result).toBeUndefined();
  });
});
