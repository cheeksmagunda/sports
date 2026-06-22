// Fetches the slate's tip-relative freeze target for the waiting countdown.
// Separate from useLineupData so the lineup display path stays untouched: the
// target only matters before a freeze, and it changes at most once a day (job1
// writes slate_meta at 13:00 UTC), so a slow poll is plenty. Best-effort --
// any failure leaves the target null and the loader shows a neutral caption.

import { useEffect, useState } from "react";
import { fetchSlateTiming } from "../lib/api";

const POLL_MS = 120_000;

export function useSlateTiming(): { freezeTargetUtc: string | null } {
  const [freezeTargetUtc, setTarget] = useState<string | null>(null);

  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const tick = async () => {
      try {
        const timing = await fetchSlateTiming();
        if (!stopped) setTarget(timing?.freeze_target_utc ?? null);
      } catch {
        if (!stopped) setTarget(null);
      }
      if (!stopped) timer = setTimeout(tick, POLL_MS);
    };
    void tick();

    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
    };
  }, []);

  return { freezeTargetUtc };
}
