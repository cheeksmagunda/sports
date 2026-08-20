// Polls /watchdog/today for the header status dot. Fixed-interval poll
// (matches useSlateTiming's cadence) -- this is ambient chrome, not the
// sweat-mode signal Phase 3's live box scores are, so it doesn't need
// visibility-aware pausing.

import { useEffect, useState } from "react";
import { fetchWatchdogToday, type WatchdogToday } from "../lib/api";

const POLL_MS = 120_000;

export function useWatchdogStatus(): WatchdogToday["status"] | null {
  const [status, setStatus] = useState<WatchdogToday["status"] | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const data = await fetchWatchdogToday();
        if (!cancelled) setStatus(data.status);
      } catch {
        // Watchdog itself being unreachable isn't a second alert -- leave
        // the dot at its last-known state rather than flipping to an
        // error look for what's likely a transient network blip.
      }
    }

    poll();
    const id = setInterval(poll, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return status;
}
