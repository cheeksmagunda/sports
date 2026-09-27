// NHL Oracle API client.
//
// Hosted NHL HTTP API is not live yet (see nhl-oracle/STATUS.md). This
// module declares the expected contract so the shell can wire against
// a future nhl-api service under nhl-staging. Until that service exists,
// callers treat 404 / network failure as "not ready" rather than a hard
// product error.
//
// Expected endpoints (mirror WNBA read-only surface, NHL-owned):
//   GET /health              -> { status: "ok" | "degraded", ... }
//   GET /slate/{YYYY-MM-DD}  -> slate timing / pool summary (TODO backend)
//   GET /lineup/{YYYY-MM-DD} -> frozen five-card ordered lineup (TODO backend)
//
// Slot multipliers when live: (2.0, 1.8, 1.6, 1.4, 1.2); boost regime none
// until every NHL team has played (#325).

import { fetchPublic } from "./http";

export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export function localSlateDate(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export type HealthStatus = {
  status: "ok" | "degraded" | "unavailable";
  detail?: string;
  checked_at?: string;
};

export type SlateTiming = {
  slate_date: string;
  first_puck_drop_utc: string | null;
  contest_lock_utc: string | null;
  freeze_lead_minutes: number;
  freeze_target_utc: string | null;
};

export type PlayerProjection = {
  player_id: number;
  display_name: string;
  team: string;
  opponent: string;
  position: "C" | "W" | "D" | "G" | string;
  card_boost: number;
  pred_real_score_p50: number;
};

export type FrozenLineupPayload = {
  player_ids: number[];
  slot_multipliers: number[];
  lineup_score_p50: number;
  per_player?: PlayerProjection[];
};

export type FrozenLineup = {
  slate_date: string;
  model_sha: string;
  frozen_at: string;
  lineup: FrozenLineupPayload;
  entry_recommendation: "enter" | "skip" | "enter_with_caveat";
  freeze_seq: number;
};

export async function fetchHealth(): Promise<HealthStatus> {
  try {
    const r = await fetchPublic(`${API_URL}/health`);
    if (r.status === 404) {
      return {
        status: "unavailable",
        detail: "GET /health not implemented yet (hosted NHL API pending)",
      };
    }
    if (!r.ok) {
      return { status: "degraded", detail: `HTTP ${r.status}` };
    }
    const body = (await r.json()) as Partial<HealthStatus>;
    return {
      status: body.status === "degraded" ? "degraded" : "ok",
      detail: typeof body.detail === "string" ? body.detail : undefined,
      checked_at: new Date().toISOString(),
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : "network error";
    return { status: "unavailable", detail: message };
  }
}

// TODO(nhl-api): implement when hosted NHL API serves slate timing.
export async function fetchSlateTiming(
  date = localSlateDate(),
): Promise<SlateTiming | null> {
  const r = await fetchPublic(`${API_URL}/slate/${date}`);
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return (await r.json()) as SlateTiming;
}

// TODO(nhl-api): implement when hosted NHL API serves frozen lineups.
export async function fetchLineupForDate(
  date: string,
): Promise<FrozenLineup | null> {
  const r = await fetchPublic(`${API_URL}/lineup/${date}`);
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return (await r.json()) as FrozenLineup;
}

export async function fetchLatestLineup(): Promise<FrozenLineup | null> {
  return fetchLineupForDate(localSlateDate());
}
