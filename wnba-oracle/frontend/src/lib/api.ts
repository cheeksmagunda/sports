export type FrozenLineupPayload = {
  player_ids: number[];
  slot_multipliers: number[];
  lineup_score_p10: number;
  lineup_score_p50: number;
  lineup_score_p90: number;
  per_player?: PlayerProjection[];
};

export type PlayerProjection = {
  player_id: number;
  display_name: string;
  team: string;
  opponent: string;
  position: "G" | "F" | "C" | string;
  card_boost: number;
  pred_real_score_p50: number;
  pred_minutes_p10: number;
  pred_minutes_p50: number;
  pred_minutes_p90: number;
};

export type FrozenLineup = {
  slate_date: string;
  model_sha: string;
  payout_regime: string;
  frozen_at: string;
  lineup: FrozenLineupPayload;
  entry_recommendation: "enter" | "skip" | "enter_with_caveat";
  expected_payout: number;
  metadata_json: unknown;
};

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function fetchLatestLineup(): Promise<FrozenLineup | null> {
  const today = new Date().toISOString().slice(0, 10);
  const r = await fetch(`${API_URL}/lineup/${today}`);
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return (await r.json()) as FrozenLineup;
}
