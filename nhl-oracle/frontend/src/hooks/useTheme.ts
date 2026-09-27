import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "nhl-oracle.theme";
type Theme = "light" | "dark";

function readInitialTheme(): Theme {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    // private mode / disabled storage
  }
  if (typeof window !== "undefined" && window.matchMedia) {
    return window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }
  return "dark";
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(readInitialTheme);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      // storage may be disabled
    }
  }, [theme]);

  const toggle = useCallback(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const supportsVT = "startViewTransition" in document;
    if (supportsVT && !reduce) {
      document.startViewTransition(() =>
        setTheme((t) => (t === "dark" ? "light" : "dark")),
      );
    } else {
      setTheme((t) => (t === "dark" ? "light" : "dark"));
    }
  }, []);

  return { theme, toggle } as const;
}
