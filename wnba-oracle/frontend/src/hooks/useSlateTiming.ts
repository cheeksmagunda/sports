// Fetches the slate's tip-relative freeze target for the waiting countdown.
// Separate from useLineupData so the lineup display path stays untouched: the
// target only matters before a freeze, and it changes at most once a day (job1
// writes slate_meta at 13:00 UTC), so a slow poll is plenty. Best-effort --
// any failure leaves the target null and the loader shows a neutral caption.

import { useEffect, useState } from "react";
import { fetchSlateTiming } from "../lib/api";

const POLL_MS = 120_000;

interface State {
  slateDate: string | null;
  firstTipUtc: string | null;
  contestLockUtc: string | null;
  freezeTargetUtc: string | null;
  picksPaused: boolean;
  resumesOn: string | null;
  // Distinguishes a genuine 404 (no slate row for today at all) from
  // "slate exists but has no freeze target yet" -- both otherwise
  // collapse to the same null freezeTargetUtc. useSlateLifecycle needs
  // this split for NO_SLATE detection.
  slateExists: boolean;
}

const INITIAL_STATE: State = {
  slateDate: null,
  firstTipUtc: null,
  contestLockUtc: null,
  freezeTargetUtc: null,
  picksPaused: false,
  resumesOn: null,
  slateExists: false,
};

export function useSlateTiming(): State {
  const [state, setState] = useState<State>(INITIAL_STATE);

  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const tick = async () => {
      try {
        const timing = await fetchSlateTiming();
        if (!stopped) {
          setState({
            slateDate: timing?.slate_date ?? null,
            firstTipUtc: timing?.first_tip_utc ?? null,
            contestLockUtc: timing?.contest_lock_utc ?? null,
            freezeTargetUtc: timing?.freeze_target_utc ?? null,
            picksPaused: timing?.picks_paused ?? false,
            resumesOn: timing?.resumes_on ?? null,
            slateExists: timing !== null,
          });
        }
      } catch {
        if (!stopped) setState(INITIAL_STATE);
      }
      if (!stopped) timer = setTimeout(tick, POLL_MS);
    };
    void tick();

    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
    };
  }, []);

  return state;
}
