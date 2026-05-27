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

// ?demo=1 returns a synthetic frozen lineup so the UI can be screenshotted
// before the first real cron-job1 fire. Defined inside the
// import.meta.env.DEV block so esbuild drops the whole fixture + lookup
// from production builds (verified: zero references to fixture players
// in the prod chunk).
let getDemoFixture: (() => FrozenLineup) | null = null;
if (import.meta.env.DEV) {
  getDemoFixture = () => ({
    slate_date: new Date().toISOString().slice(0, 10),
    model_sha: "abc123def4567890fedcba9876543210",
    payout_regime: "top_20",
    frozen_at: new Date().toISOString(),
    entry_recommendation: "enter",
    expected_payout: 1.42,
    metadata_json: null,
    lineup: {
      player_ids: [1, 2, 3, 4, 5],
      slot_multipliers: [1.5, 1.3, 1.2, 1.1, 1.0],
      lineup_score_p10: 124.5,
      lineup_score_p50: 182.7,
      lineup_score_p90: 241.1,
      per_player: [
        { player_id: 1, display_name: "A'ja Wilson",     team: "LVA", opponent: "NYL", position: "F", card_boost: 0.50, pred_real_score_p50: 42.3, pred_minutes_p10: 32, pred_minutes_p50: 35, pred_minutes_p90: 38 },
        { player_id: 2, display_name: "Breanna Stewart", team: "NYL", opponent: "LVA", position: "F", card_boost: 0.30, pred_real_score_p50: 38.1, pred_minutes_p10: 30, pred_minutes_p50: 34, pred_minutes_p90: 37 },
        { player_id: 3, display_name: "Sabrina Ionescu", team: "NYL", opponent: "LVA", position: "G", card_boost: 0.00, pred_real_score_p50: 33.5, pred_minutes_p10: 28, pred_minutes_p50: 32, pred_minutes_p90: 35 },
        { player_id: 4, display_name: "Caitlin Clark",   team: "IND", opponent: "CHI", position: "G", card_boost: 0.75, pred_real_score_p50: 31.8, pred_minutes_p10: 28, pred_minutes_p50: 33, pred_minutes_p90: 36 },
        { player_id: 5, display_name: "Napheesa Collier",team: "MIN", opponent: "SEA", position: "F", card_boost: 0.20, pred_real_score_p50: 29.6, pred_minutes_p10: 26, pred_minutes_p50: 30, pred_minutes_p90: 34 },
      ],
    },
  });
}

function demoFixture(): FrozenLineup | null {
  if (!getDemoFixture) return null;
  if (typeof window === "undefined") return null;
  if (new URLSearchParams(window.location.search).get("demo") !== "1") return null;
  return getDemoFixture();
}

export async function fetchLatestLineup(): Promise<FrozenLineup | null> {
  const demo = demoFixture();
  if (demo) return demo;
  const today = new Date().toISOString().slice(0, 10);
  const r = await fetch(`${API_URL}/lineup/${today}`);
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return (await r.json()) as FrozenLineup;
}
