import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SWRConfig } from "swr";
import { Theme } from "@radix-ui/themes";
import { OnboardingWizard } from "./wizard";

declare global {
  // eslint-disable-next-line no-var
  var fetch: typeof window.fetch;
  // eslint-disable-next-line no-var
  var IS_REACT_ACT_ENVIRONMENT: boolean | undefined;
}

type FetchCall = { url: string; method: string; body?: unknown };

async function flush() {
  await act(async () => {
    await Promise.resolve();
  });
}

async function waitForText(root: HTMLElement, text: string, present = true) {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    await flush();
    const hasText = root.textContent?.includes(text) ?? false;
    if ((present && hasText) || (!present && !hasText)) {
      return;
    }
  }
  throw new Error(`Timed out waiting for ${present ? "presence" : "absence"} of text: ${text}`);
}

function renderWizard() {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);

  act(() => {
    root.render(
      <Theme>
        <SWRConfig value={{ provider: () => new Map() }}>
          <OnboardingWizard />
        </SWRConfig>
      </Theme>,
    );
  });

  return {
    container,
    unmount: () => {
      act(() => {
        root.unmount();
      });
      container.remove();
    },
  };
}

describe("OnboardingWizard", () => {
  let onboardingStatus = {
    id: "ws-1",
    slug: "default",
    name: "Default Workspace",
    onboarding_completed_at: null,
    project_count: 0,
    provider_count: 0,
    requires_onboarding: true,
  };
  const calls: FetchCall[] = [];

  beforeEach(() => {
    globalThis.IS_REACT_ACT_ENVIRONMENT = true;
    vi.stubGlobal(
      "ResizeObserver",
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    );
    calls.length = 0;
    onboardingStatus = {
      id: "ws-1",
      slug: "default",
      name: "Default Workspace",
      onboarding_completed_at: null,
      project_count: 0,
      provider_count: 0,
      requires_onboarding: true,
    };

    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        const method = init?.method ?? "GET";
        const body = init?.body ? JSON.parse(String(init.body)) : undefined;
        calls.push({ url, method, body });

        if (url === "/api/workspaces/me" && method === "GET") {
          return new Response(JSON.stringify(onboardingStatus), {
            status: 200,
            headers: { "content-type": "application/json" },
          });
        }
        if (url === "/api/projects" && method === "POST") {
          onboardingStatus.project_count = 1;
          return new Response(JSON.stringify({ id: "project-1" }), {
            status: 201,
            headers: { "content-type": "application/json" },
          });
        }
        if (url === "/api/providers" && method === "POST") {
          onboardingStatus.provider_count = 1;
          return new Response(JSON.stringify({ id: "provider-1" }), {
            status: 201,
            headers: { "content-type": "application/json" },
          });
        }
        if (url === "/api/workspaces/me/onboarding" && method === "POST") {
          onboardingStatus = {
            ...onboardingStatus,
            name: String(body?.name || onboardingStatus.name),
            onboarding_completed_at: "2026-04-19T00:00:00Z",
            requires_onboarding: false,
          };
          return new Response(JSON.stringify(onboardingStatus), {
            status: 200,
            headers: { "content-type": "application/json" },
          });
        }
        return new Response("Not found", { status: 404 });
      }) as typeof fetch,
    );
  });

  afterEach(() => {
    document.body.innerHTML = "";
    vi.unstubAllGlobals();
  });

  it("can be skipped and resurfaces on a new load", async () => {
    const view = renderWizard();
    await waitForText(document.body, "Name your workspace");

    const skipButton = Array.from(document.body.querySelectorAll("button")).find((node) =>
      node.textContent?.includes("Skip for now"),
    );
    expect(skipButton).toBeTruthy();
    act(() => {
      (skipButton as HTMLButtonElement).click();
    });
    await waitForText(document.body, "Name your workspace", false);

    view.unmount();
    const second = renderWizard();
    await waitForText(document.body, "Name your workspace");
    second.unmount();
  });

  it("stays hidden when onboarding is already complete", async () => {
    onboardingStatus = {
      ...onboardingStatus,
      onboarding_completed_at: "2026-04-19T00:00:00Z",
      project_count: 1,
      provider_count: 1,
      requires_onboarding: false,
    };
    const view = renderWizard();
    await flush();
    expect(view.container.textContent || "").not.toContain("Name your workspace");
    expect(calls.some((call) => call.url === "/api/workspaces/me" && call.method === "GET")).toBe(true);
  });
});
