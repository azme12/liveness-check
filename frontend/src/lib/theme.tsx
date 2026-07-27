"use client";

import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { api } from "@/lib/api";

export type ThemeMode = "light" | "dark" | "system";

type ThemeContextValue = {
  theme: ThemeMode;
  resolved: "light" | "dark";
  setTheme: (theme: ThemeMode) => void;
  hydrateTheme: (theme: ThemeMode) => void;
};

const ThemeContext = createContext<ThemeContextValue>({
  theme: "system",
  resolved: "dark",
  setTheme: () => undefined,
  hydrateTheme: () => undefined,
});

function resolveTheme(theme: ThemeMode): "light" | "dark" {
  if (theme === "light" || theme === "dark") return theme;
  if (typeof window === "undefined") return "dark";
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

function applyTheme(theme: ThemeMode) {
  const resolved = resolveTheme(theme);
  document.documentElement.setAttribute("data-theme", resolved);
  document.documentElement.style.colorScheme = resolved;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeMode>("system");
  const [resolved, setResolved] = useState<"light" | "dark">("dark");

  useEffect(() => {
    const stored = localStorage.getItem("trustanova_theme") as ThemeMode | null;
    const initial = stored && ["light", "dark", "system"].includes(stored) ? stored : "system";
    setThemeState(initial);
    setResolved(resolveTheme(initial));
    applyTheme(initial);

    const mq = window.matchMedia("(prefers-color-scheme: light)");
    const onChange = () => {
      const current = (localStorage.getItem("trustanova_theme") as ThemeMode) || "system";
      if (current === "system") {
        setResolved(resolveTheme("system"));
        applyTheme("system");
      }
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const setTheme = useCallback((next: ThemeMode) => {
    setThemeState(next);
    setResolved(resolveTheme(next));
    localStorage.setItem("trustanova_theme", next);
    applyTheme(next);
    api("/api/auth/theme", { method: "PATCH", body: JSON.stringify({ theme: next }) }).catch(
      () => undefined,
    );
  }, []);

  const hydrateTheme = useCallback((next: ThemeMode) => {
    setThemeState(next);
    setResolved(resolveTheme(next));
    localStorage.setItem("trustanova_theme", next);
    applyTheme(next);
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, resolved, setTheme, hydrateTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
