import type { ReactNode } from "react";
import { useTheme } from "../hooks/useTheme";
import { Footer } from "./Footer";
import { Header } from "./Header";

const APP_VERSION =
  (import.meta.env.VITE_APP_VERSION as string | undefined) ?? "v0.1.0";

interface Props {
  slateDateDisplay?: string | null;
  apiStatus?: string;
  children: ReactNode;
}

export function Shell({
  slateDateDisplay = null,
  apiStatus = "pending",
  children,
}: Props) {
  const { theme, toggle } = useTheme();

  return (
    <div className="app">
      <Header
        theme={theme}
        onThemeToggle={toggle}
        slateDateDisplay={slateDateDisplay}
      />
      <main id="main-content">{children}</main>
      <Footer appVersion={APP_VERSION} apiStatus={apiStatus} />
    </div>
  );
}
