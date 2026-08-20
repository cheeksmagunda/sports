// Shared page chrome: theme-aware Header + Footer around page-specific
// content. Every route uses this so nav (wordmark -> /, History link,
// watchdog dot -> /system) works from anywhere, not just Tonight.

import type { ReactNode } from "react";
import { useTheme } from "../hooks/useTheme";
import type { FrozenLineup } from "../lib/api";
import { Footer } from "./Footer";
import { Header } from "./Header";

const APP_VERSION =
  (import.meta.env.VITE_APP_VERSION as string | undefined) ?? "v0.2.0";

interface Props {
  slateDateDisplay?: string | null;
  frozenAtDisplay?: string | null;
  lineup?: FrozenLineup | null;
  children: ReactNode;
}

export function Shell({
  slateDateDisplay = null,
  frozenAtDisplay = null,
  lineup = null,
  children,
}: Props) {
  const { theme, toggle } = useTheme();

  return (
    <div className="app">
      <Header
        theme={theme}
        onThemeToggle={toggle}
        slateDateDisplay={slateDateDisplay}
        frozenAtDisplay={frozenAtDisplay}
      />
      <main id="main-content">
        {children}
      </main>
      <Footer lineup={lineup} appVersion={APP_VERSION} />
    </div>
  );
}
