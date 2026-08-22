// Morning view. Operator opens this once per day. Header → SlateBand →
// Slip → Footer. While the backend hasn't frozen today's lineup yet,
// OracleLoader holds the canvas with a T-minus countdown. Once a lineup
// exists and its games start, useSlateLifecycle flips the view through
// frozen_pre_tip -> live -> final as ESPN reports it.

import { useEffect, useMemo, useState } from "react";
import { ErrorState } from "../components/ErrorState";
import { OracleLoader } from "../components/OracleLoader";
import { Shell } from "../components/Shell";
import { SlateBand } from "../components/SlateBand";
import { Slip } from "../components/Slip";
import { useLiveBoxScores } from "../hooks/useLiveBoxScores";
import { useSlateLifecycle } from "../hooks/useSlateLifecycle";
import {
  effectiveLockUtc,
  getRecommendationActionability,
} from "../lib/actionability";
import { localSlateDate } from "../lib/api";
import { combineBoxLines } from "../lib/playerMatch";

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
  const intro = useFirstMountLoader();
  const lifecycle = useSlateLifecycle();
  const boxLines = useLiveBoxScores(lifecycle.games);
  const [actionabilityNowMs, setActionabilityNowMs] = useState(() => Date.now());

  useEffect(() => {
    // A newly fetched freeze needs a fresh comparison clock. Defer the update
    // so the effect never performs a synchronous state write.
    const refreshTimer = setTimeout(() => setActionabilityNowMs(Date.now()), 0);
    const lockUtc = effectiveLockUtc(
      lifecycle.contestLockUtc,
      lifecycle.firstTipUtc,
    );
    const lockMs = lockUtc ? Date.parse(lockUtc) : Number.NaN;
    if (Number.isNaN(lockMs)) return () => clearTimeout(refreshTimer);

    // Re-evaluate just after the strict lock boundary even when no network
    // poll or scoreboard update happens at that instant.
    const lockTimer = setTimeout(
      () => setActionabilityNowMs(Date.now()),
      Math.max(0, lockMs - Date.now() + 1),
    );
    return () => {
      clearTimeout(refreshTimer);
      clearTimeout(lockTimer);
    };
  }, [
    lifecycle.contestLockUtc,
    lifecycle.firstTipUtc,
    lifecycle.lineup?.frozen_at,
    lifecycle.lineupFresh,
    lifecycle.picksPaused,
    lifecycle.timingSlateDate,
  ]);

  const view = useMemo(() => {
    if (lifecycle.picksPaused) {
      return { kind: "paused" as const, resumesOn: lifecycle.resumesOn };
    }
    if (lifecycle.state === "error") {
      return { kind: "error" as const, detail: lifecycle.error };
    }
    if (lifecycle.lineup) {
      return { kind: "lineup" as const, lineup: lifecycle.lineup };
    }
    if (lifecycle.state === "no_slate" || lifecycle.state === "pre_freeze") {
      return { kind: "waiting" as const };
    }
    return { kind: "loading" as const };
  }, [
    lifecycle.picksPaused,
    lifecycle.resumesOn,
    lifecycle.state,
    lifecycle.error,
    lifecycle.lineup,
  ]);

  const combined = useMemo(() => {
    if (view.kind !== "lineup") return undefined;
    return combineBoxLines(view.lineup.lineup.per_player ?? [], boxLines);
  }, [view, boxLines]);

  const gamesRemaining = lifecycle.games.filter((g) => g.state !== "post").length;

  const slateDateDisplay = fmtSlateDate(
    view.kind === "lineup" ? view.lineup.slate_date : null,
  );
  const frozenAtDisplay = fmtFrozenAt(
    view.kind === "lineup" ? view.lineup.frozen_at : null,
  );
  const recommendationActionability =
    view.kind === "lineup"
      ? getRecommendationActionability({
          recommendation: view.lineup.entry_recommendation,
          lineupSlateDate: view.lineup.slate_date,
          timingSlateDate: lifecycle.timingSlateDate,
          todaySlateDate: localSlateDate(),
          frozenAtUtc: view.lineup.frozen_at,
          frozenVia: view.lineup.frozen_via,
          lineupFresh: lifecycle.lineupFresh,
          picksPaused: lifecycle.picksPaused,
          firstTipUtc: lifecycle.firstTipUtc,
          contestLockUtc: lifecycle.contestLockUtc,
          nowMs: actionabilityNowMs,
        })
      : undefined;

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
        freezeTargetUtc={lifecycle.freezeTargetUtc}
      />
      <Shell
        slateDateDisplay={slateDateDisplay}
        frozenAtDisplay={frozenAtDisplay}
        lineup={view.kind === "lineup" ? view.lineup : null}
      >
        <SlateBand
          lineup={view.kind === "lineup" ? view.lineup : null}
          lifecycleState={lifecycle.state}
          combined={combined}
          gamesRemaining={gamesRemaining}
          recommendationActionability={recommendationActionability}
        />
        <main
          id="lineup"
          aria-label="Frozen morning lineup"
          aria-busy={view.kind === "loading" || view.kind === "waiting"}
        >
          {view.kind === "lineup" ? (
            <Slip
              lineup={view.lineup}
              boxLines={boxLines}
              lifecycleState={lifecycle.state}
            />
          ) : view.kind === "error" ? (
            <ErrorState
              title="Can't reach the picker server"
              copy="The lineup API isn't responding. Check VITE_API_URL or wait a moment."
              detail={view.detail}
              onRetry={lifecycle.refresh}
            />
          ) : view.kind === "paused" ? (
            <ErrorState
              title="Picks are paused"
              copy={
                view.resumesOn
                  ? `The oracle is taking a short break. Back for the ${fmtSlateDate(view.resumesOn)} slate.`
                  : "The oracle is taking a short break. Check back soon."
              }
            />
          ) : null}
        </main>
      </Shell>
    </>
  );
}
