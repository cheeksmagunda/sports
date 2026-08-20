// Polls ESPN summaries for the relevant games' box lines. Only polls on
// a timer while at least one relevant game is live ("in"); fetches once
// (no repeat) when games are final since post-game stats don't change,
// and stops entirely once nothing is live. Pauses the repeat timer while
// the tab is hidden and refreshes immediately on return, reusing the
// visibilitychange pattern from useLineupData.

import { useEffect, useRef, useState } from "react";
import { fetchSummary, type PlayerBoxLine, type ScoreboardGame } from "../lib/espn";

const POLL_MS = 30_000;

export function useLiveBoxScores(games: ScoreboardGame[]): PlayerBoxLine[] {
  const [boxLines, setBoxLines] = useState<PlayerBoxLine[]>([]);
  const gamesRef = useRef(games);
  // Refs can't be written during render -- keep it current after every
  // render instead, so the polling effect below always reads the latest
  // games regardless of when its async tick() closure fires.
  useEffect(() => {
    gamesRef.current = games;
  });

  // Games' identity/state as a stable primitive so the polling effect
  // only re-runs when what it actually cares about changes, not on every
  // re-render of a new `games` array reference with the same content.
  const depKey = games.map((g) => `${g.eventId}:${g.state}`).join(",");

  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const fetchOnce = async () => {
      const active = gamesRef.current.filter((g) => g.state === "in" || g.state === "post");
      if (active.length === 0) {
        if (!stopped) setBoxLines([]);
        return;
      }
      const results = await Promise.allSettled(active.map((g) => fetchSummary(g.eventId)));
      if (stopped) return;
      setBoxLines(results.flatMap((r) => (r.status === "fulfilled" ? r.value : [])));
    };

    const tick = async () => {
      if (stopped) return;
      await fetchOnce();
      const anyLive = gamesRef.current.some((g) => g.state === "in");
      if (!stopped && anyLive) timer = setTimeout(tick, POLL_MS);
    };

    const onVisibility = () => {
      if (document.hidden) {
        if (timer) {
          clearTimeout(timer);
          timer = null;
        }
      } else {
        if (timer) clearTimeout(timer);
        void tick();
      }
    };

    if (gamesRef.current.some((g) => g.state === "in" || g.state === "post")) {
      void tick();
    }
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisibility);
    };
    // depKey captures every reactive value this effect reads from games.
  }, [depKey]);

  return boxLines;
}
