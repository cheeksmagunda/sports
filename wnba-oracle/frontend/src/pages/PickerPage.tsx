// Morning view. Operator opens this once per day. Header → SlateBand →
// 5-card grid → Footer. While the backend hasn't frozen today's lineup
// yet, OracleLoader holds the canvas with a T-minus countdown.

import { useEffect, useMemo, useState } from "react";
import { ErrorState } from "../components/ErrorState";
import { Footer } from "../components/Footer";
import { Header } from "../components/Header";
import { LineupStack } from "../components/LineupStack";
import { OracleLoader } from "../components/OracleLoader";
import { SlateBand } from "../components/SlateBand";
import { useLineupData } from "../hooks/useLineupData";
import { useTheme } from "../hooks/useTheme";

const APP_VERSION =
  (import.meta.env.VITE_APP_VERSION as string | undefined) ?? "v0.2.0";

// Brief intro animation on first paint so the page never flashes the
// bare canvas before the first network round-trip resolves. Honors
// prefers-reduced-motion.
function useFirstMountLoader() {
  const [visible, setVisible] = useState(true);
  const [fading, setFading] = useState(false);
  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const total = reduce ? 400 : 1500;
    const fadeAt = total - 400;
    const fadeT = setTimeout(() => setFading(true), fadeAt);
    const hideT = setTimeout(() => setVisible(false), total);
    return () => {
      clearTimeout(fadeT);
      clearTimeout(hideT);
    };
  }, []);
  return { visible, fading };
}

function fmtSlateDate(iso: string | null | undefined): string | null {
  if (!iso) return null;
  // Parse YYYY-MM-DD at noon local so DST doesn't shift the day. The
  // slate concept is calendar-based, not UTC.
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return null;
  const date = new Date(y, m - 1, d, 12, 0, 0);
  return date
    .toLocaleDateString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
      year: "numeric",
    })
    .toUpperCase()
    .replaceAll(",", " ·");
}

function fmtFrozenAt(iso: string | null | undefined): string | null {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleTimeString(undefined, {
      hour: "numeric",
      minute: "2-digit",
      timeZoneName: "short",
    });
  } catch {
    return null;
  }
}

export function PickerPage() {
  const { theme, toggle } = useTheme();
  const intro = useFirstMountLoader();
  const { uiState, lineup, error, refresh } = useLineupData();

  const view = useMemo(() => {
    if (uiState === "error") {
      return { kind: "error" as const, detail: error };
    }
    if (lineup) {
      return { kind: "lineup" as const, lineup };
    }
    if (uiState === "no_lineup") {
      return { kind: "waiting" as const };
    }
    return { kind: "loading" as const };
  }, [uiState, lineup, error]);

  const slateDateDisplay = fmtSlateDate(
    view.kind === "lineup" ? view.lineup.slate_date : null,
  );
  const frozenAtDisplay = fmtFrozenAt(
    view.kind === "lineup" ? view.lineup.frozen_at : null,
  );

  // Show loader during intro AND while waiting for a freeze. Unmount
  // once a lineup arrives so cards render at full opacity. `fading`
  // applies only during the intro hand-off window — after that we want
  // the waiting-state loader at full opacity, not lingering at 0.
  const loaderVisible =
    intro.visible || view.kind === "loading" || view.kind === "waiting";
  const loaderMode = intro.visible ? "intro" : "waiting";
  const loaderFading = intro.fading && intro.visible;

  return (
    <>
      <a className="skip-link" href="#lineup">
        Skip to lineup
      </a>
      <OracleLoader
        visible={loaderVisible}
        fading={loaderFading}
        mode={loaderMode}
      />
      <div className="app">
        <Header
          theme={theme}
          onThemeToggle={toggle}
          slateDateDisplay={slateDateDisplay}
          frozenAtDisplay={frozenAtDisplay}
        />
        {view.kind === "lineup" ? <SlateBand lineup={view.lineup} /> : null}
        <main
          id="lineup"
          aria-label="Frozen morning lineup"
          aria-busy={view.kind === "loading" || view.kind === "waiting"}
        >
          {view.kind === "lineup" ? (
            <LineupStack lineup={view.lineup} />
          ) : view.kind === "error" ? (
            <ErrorState
              title="Can't reach the picker server"
              copy="The lineup API isn't responding. Check VITE_API_URL or wait a moment."
              detail={view.detail}
              onRetry={refresh}
            />
          ) : null}
        </main>
        <Footer
          lineup={view.kind === "lineup" ? view.lineup : null}
          appVersion={APP_VERSION}
        />
      </div>
    </>
  );
}
