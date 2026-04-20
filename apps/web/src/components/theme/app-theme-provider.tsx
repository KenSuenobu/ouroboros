"use client";

import { Theme } from "@radix-ui/themes";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

type ThemePreference = "system" | "light" | "dark";
type ThemeAppearance = "light" | "dark";

export const STORAGE_KEY = "ouroboros-theme-preference";
const DARK_SCHEME_QUERY = "(prefers-color-scheme: dark)";

type ThemePreferenceContextValue = {
  appearance: ThemeAppearance;
  preference: ThemePreference;
  toggleTheme: () => void;
  setPreference: (preference: ThemePreference) => void;
};

const ThemePreferenceContext = createContext<ThemePreferenceContextValue | null>(null);

function isThemePreference(value: string | null): value is ThemePreference {
  return value === "system" || value === "light" || value === "dark";
}

function getStoredPreference(): ThemePreference {
  if (typeof window === "undefined") {
    return "system";
  }

  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return isThemePreference(stored) ? stored : "system";
  } catch {
    return "system";
  }
}

export function resolveAppearance(preference: ThemePreference, prefersDark: boolean): ThemeAppearance {
  if (preference === "system") {
    return prefersDark ? "dark" : "light";
  }

  return preference;
}

export function AppThemeProvider({ children }: { children: ReactNode }) {
  const [preference, setPreference] = useState<ThemePreference>(() => getStoredPreference());
  const [prefersDark, setPrefersDark] = useState<boolean>(() => {
    if (typeof window === "undefined") {
      return false;
    }
    return window.matchMedia(DARK_SCHEME_QUERY).matches;
  });

  useEffect(() => {
    if (typeof window === "undefined") {
      return undefined;
    }

    const media = window.matchMedia(DARK_SCHEME_QUERY);
    const onMediaChange = (event: MediaQueryListEvent) => {
      setPrefersDark(event.matches);
    };

    setPrefersDark(media.matches);
    media.addEventListener("change", onMediaChange);

    return () => {
      media.removeEventListener("change", onMediaChange);
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    try {
      if (preference === "system") {
        window.localStorage.removeItem(STORAGE_KEY);
        return;
      }

      window.localStorage.setItem(STORAGE_KEY, preference);
    } catch {
      // Storage unavailable (e.g. private browsing with storage disabled); skip persistence.
    }
  }, [preference]);

  const appearance = resolveAppearance(preference, prefersDark);

  const toggleTheme = useCallback(() => {
    setPreference((previousPreference) => {
      const previousAppearance = resolveAppearance(previousPreference, prefersDark);
      return previousAppearance === "dark" ? "light" : "dark";
    });
  }, [prefersDark]);

  const value = useMemo<ThemePreferenceContextValue>(
    () => ({
      appearance,
      preference,
      toggleTheme,
      setPreference,
    }),
    [appearance, preference, toggleTheme],
  );

  return (
    <ThemePreferenceContext.Provider value={value}>
      <Theme accentColor="iris" grayColor="slate" radius="medium" appearance={appearance}>
        {children}
      </Theme>
    </ThemePreferenceContext.Provider>
  );
}

export function useThemePreference() {
  const context = useContext(ThemePreferenceContext);
  if (!context) {
    throw new Error("useThemePreference must be used inside AppThemeProvider");
  }
  return context;
}
