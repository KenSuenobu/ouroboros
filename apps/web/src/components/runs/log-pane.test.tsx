import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Theme } from "@radix-ui/themes";
import { LogPane } from "./log-pane";
import type { RunEvent } from "@/lib/api/types";

declare global {
  // eslint-disable-next-line no-var
  var IS_REACT_ACT_ENVIRONMENT: boolean | undefined;
}

function renderPane(events: RunEvent[], isRunning = true) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  act(() => {
    root.render(
      <Theme>
        <LogPane stepId="step-1" events={events} isRunning={isRunning} />
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

describe("LogPane", () => {
  beforeEach(() => {
    globalThis.IS_REACT_ACT_ENVIRONMENT = true;
    Object.defineProperty(Element.prototype, "scrollIntoView", {
      configurable: true,
      value: vi.fn(),
      writable: true,
    });
  });

  afterEach(() => {
    document.body.innerHTML = "";
    vi.restoreAllMocks();
  });

  it("renders only logs from the matching step", () => {
    const events: RunEvent[] = [
      {
        run_id: "run-1",
        type: "step.log",
        payload: { step_id: "step-1", stream: "stdout", line: "hello\n" },
        timestamp: "2026-04-19T00:00:00Z",
      },
      {
        run_id: "run-1",
        type: "step.log",
        payload: { step_id: "step-2", stream: "stderr", line: "ignore\n" },
        timestamp: "2026-04-19T00:00:01Z",
      },
    ];
    const view = renderPane(events, true);
    expect(view.container.textContent).toContain("[stdout] hello");
    expect(view.container.textContent).not.toContain("ignore");
    view.unmount();
  });

  it("shows waiting state when running with no logs", () => {
    const view = renderPane([], true);
    expect(view.container.textContent).toContain("Waiting for log output");
    view.unmount();
  });
});
