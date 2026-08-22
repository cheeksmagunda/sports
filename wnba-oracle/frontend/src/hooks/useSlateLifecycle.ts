// Derives the slate lifecycle state from our API (has a lineup? is it
// paused?) plus ESPN (are the relevant games pre/in/post?). Composes
// useLineupData and useSlateTiming rather than duplicating their fetches,
// and owns one more poll: today's ESPN scoreboard, scoped to the same
// local slate date the other two already use.

import { useEffect, useMemo, useState } from "react";
import { localSlateDate } from "../lib/api";
import { fetchScoreboard, toEspnDate, type ScoreboardGame } from "../lib/espn";
import { espnCode } from "../lib/teams";
import { useLineupData } from "./useLineupData";
import { useSlateTiming } from "./useSlateTiming";

export type SlateLifecycleState =
  | "paused"
  | "no_slate"
  | "pre_freeze"
  | "frozen_pre_tip"
  | "live"
  | "final"
  | "error";

const SCOREBOARD_POLL_MS = 60_000;

function relevantGames(games: ScoreboardGame[], teams: Set<string>): ScoreboardGame[] {
  if (teams.size === 0) return games;
  return games.filter((g) => teams.has(g.home.team) || teams.has(g.away.team));
}

export function useSlateLifecycle() {
  const lineupData = useLineupData();
  const slateTiming = useSlateTiming();
  const [games, setGames] = useState<ScoreboardGame[]>([]);
  const [gamesLoaded, setGamesLoaded] = useState(false);

  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const tick = async () => {
      try {
        const g = await fetchScoreboard(toEspnDate(localSlateDate()));
        if (!stopped) setGames(g);
      } catch {
        // ESPN is enrichment only -- never block lifecycle detection on
        // it. Leave games at its last-known value.
      }
      if (!stopped) {
        setGamesLoaded(true);
        timer = setTimeout(tick, SCOREBOARD_POLL_MS);
      }
    };
    void tick();

    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
    };
  }, []);

  const teams = useMemo(() => {
    const codes = (lineupData.lineup?.lineup.per_player ?? [])
      .map((p) => espnCode(p.team))
      .filter((c): c is string => Boolean(c));
    return new Set(codes);
  }, [lineupData.lineup]);

  const relevant = useMemo(() => relevantGames(games, teams), [games, teams]);

  const state: SlateLifecycleState = useMemo(() => {
    if (slateTiming.picksPaused) return "paused";
    if (lineupData.uiState === "error") return "error";

    if (lineupData.lineup) {
      if (relevant.length === 0) {
        // No ESPN match for the five yet (join miss, or ESPN briefly
        // unavailable) -- still frozen, just without lifecycle detection.
        return "frozen_pre_tip";
      }
      if (relevant.every((g) => g.state === "post")) return "final";
      if (relevant.some((g) => g.state === "in")) return "live";
      return "frozen_pre_tip";
    }

    if (lineupData.uiState === "no_lineup") {
      if (slateTiming.slateExists) return "pre_freeze";
      if (gamesLoaded && games.length === 0) return "no_slate";
      return "pre_freeze";
    }

    // idle/fetching: not yet resolved. No dedicated 8th state for this
    // in the spec's model -- pre_freeze renders the same waiting UI the
    // app already shows during this gap.
    return "pre_freeze";
  }, [
    slateTiming.picksPaused,
    slateTiming.slateExists,
    lineupData.uiState,
    lineupData.lineup,
    relevant,
    gamesLoaded,
    games.length,
  ]);

  return {
    state,
    lineup: lineupData.lineup,
    lineupFresh: lineupData.uiState === "success",
    error: lineupData.error,
    refresh: lineupData.refresh,
    timingSlateDate: slateTiming.slateDate,
    firstTipUtc: slateTiming.firstTipUtc,
    contestLockUtc: slateTiming.contestLockUtc,
    freezeTargetUtc: slateTiming.freezeTargetUtc,
    picksPaused: slateTiming.picksPaused,
    resumesOn: slateTiming.resumesOn,
    games: relevant,
  };
}
