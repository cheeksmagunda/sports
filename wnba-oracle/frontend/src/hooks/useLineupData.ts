// Frozen-lineup fetch hook. Backend only exposes /lineup/{date} +
// /lineup, no SSE broker, so we poll. Cadence: 1s on first error,
// exponential backoff up to 30s; resets when state changes.

import { useCallback, useEffect, useRef, useState } from "react";
import type { FrozenLineup } from "../lib/api";
import { fetchLatestLineup } from "../lib/api";

type UiState = "idle" | "fetching" | "success" | "error" | "no_lineup";

interface State {
  uiState: UiState;
  lineup: FrozenLineup | null;
  error: string | null;
}

export function useLineupData() {
  const [state, setState] = useState<State>({
    uiState: "idle",
    lineup: null,
    error: null,
  });
  const stateRef = useRef(state);
  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  const refresh = useCallback(async () => {
    setState((s) => ({ ...s, uiState: s.lineup ? s.uiState : "fetching" }));
    try {
      const data = await fetchLatestLineup();
      if (data) {
        setState({ uiState: "success", lineup: data, error: null });
      } else {
        setState((s) => ({
          ...s,
          uiState: "no_lineup",
          lineup: null,
          error: null,
        }));
      }
    } catch (e) {
      setState((s) => ({
        ...s,
        uiState: "error",
        error: e instanceof Error ? e.message : String(e),
      }));
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Polling fallback. Backoff resets on observed state change.
  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let delayMs = 5_000;
    let lastSnap = "";

    const tick = async () => {
      if (stopped) return;
      await refresh();
      const snap = JSON.stringify({
        ui: stateRef.current.uiState,
        date: stateRef.current.lineup?.slate_date ?? null,
      });
      if (snap !== lastSnap) {
        delayMs = 5_000;
        lastSnap = snap;
      } else {
        delayMs = Math.min(delayMs * 2, 60_000);
      }
      timer = setTimeout(tick, delayMs);
    };
    timer = setTimeout(tick, delayMs);
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
    };
  }, [refresh]);

  // Refetch when tab returns from > 60s hidden.
  useEffect(() => {
    let hiddenSince: number | null = null;
    const onVis = () => {
      if (document.hidden) {
        hiddenSince = Date.now();
      } else if (hiddenSince && Date.now() - hiddenSince > 60_000) {
        void refresh();
        hiddenSince = null;
      }
    };
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, [refresh]);

  return { ...state, refresh };
}
