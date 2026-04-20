import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppThemeProvider, STORAGE_KEY, useThemePreference } from "./app-theme-provider";

declare global {
  // eslint-disable-next-line no-var
  var IS_REACT_ACT_ENVIRONMENT: boolean | undefined;
}

type MockMediaQueryList = MediaQueryList & {
  dispatch: (matches: boolean) => void;
};

function installMatchMediaMock(initialMatches: boolean): MockMediaQueryList {
  const listeners = new Set<(event: MediaQueryListEvent) => void>();

  const mediaQueryList = {
    media: "(prefers-color-scheme: dark)",
    matches: initialMatches,
    onchange: null,
    addEventListener: (_event: "change", listener: (event: MediaQueryListEvent) => void) => {
      listeners.add(listener);
    },
    removeEventListener: (_event: "change", listener: (event: MediaQueryListEvent) => void) => {
      listeners.delete(listener);
    },
    addListener: (listener: (event: MediaQueryListEvent) => void) => {
      listeners.add(listener);
    },
    removeListener: (listener: (event: MediaQueryListEvent) => void) => {
      listeners.delete(listener);
    },
    dispatchEvent: () => true,
    dispatch: (matches: boolean) => {
      mediaQueryList.matches = matches;
      const event = { matches } as MediaQueryListEvent;
      for (const listener of listeners) {
        listener(event);
      }
    },
  } as MockMediaQueryList;

  vi.stubGlobal("matchMedia", vi.fn(() => mediaQueryList));
  return mediaQueryList;
}

function ThemeProbe() {
  const { appearance, preference, toggleTheme } = useThemePreference();
  return (
    <div>
      <span data-testid="appearance">{appearance}</span>
      <span data-testid="preference">{preference}</span>
      <button type="button" onClick={toggleTheme}>toggle</button>
    </div>
  );
}

function renderThemeProbe() {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);

  act(() => {
    root.render(
      <AppThemeProvider>
        <ThemeProbe />
      </AppThemeProvider>,
    );
  });

  return {
    getAppearance: () => container.querySelector("[data-testid='appearance']")?.textContent,
    getPreference: () => container.querySelector("[data-testid='preference']")?.textContent,
    toggle: () => {
      const button = container.querySelector("button");
      if (!(button instanceof HTMLButtonElement)) {
        throw new Error("toggle button missing");
      }
      act(() => {
        button.click();
      });
    },
    cleanup: () => {
      act(() => {
        root.unmount();
      });
      container.remove();
    },
  };
}

describe("AppThemeProvider", () => {
  let view: ReturnType<typeof renderThemeProbe> | undefined;

  beforeEach(() => {
    vi.unstubAllGlobals();
    globalThis.IS_REACT_ACT_ENVIRONMENT = true;
    window.localStorage.clear();
    document.body.innerHTML = "";
  });

  afterEach(() => {
    view?.cleanup();
    view = undefined;
  });

  it("follows system preference when no override is stored", async () => {
    const mediaQueryList = installMatchMediaMock(true);
    view = renderThemeProbe();

    expect(view.getPreference()).toBe("system");
    expect(view.getAppearance()).toBe("dark");

    act(() => {
      mediaQueryList.dispatch(false);
    });

    await vi.waitFor(() => {
      expect(view!.getAppearance()).toBe("light");
    });
  });

  it("uses stored override and persists manual toggle", async () => {
    installMatchMediaMock(true);
    window.localStorage.setItem(STORAGE_KEY, "light");
    view = renderThemeProbe();

    expect(view.getPreference()).toBe("light");
    expect(view.getAppearance()).toBe("light");

    view.toggle();

    await vi.waitFor(() => {
      expect(view!.getAppearance()).toBe("dark");
      expect(view!.getPreference()).toBe("dark");
      expect(window.localStorage.getItem(STORAGE_KEY)).toBe("dark");
    });
  });
});
