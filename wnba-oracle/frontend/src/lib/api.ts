import { getDemoMode } from "./demo";

export type Archetype =
  | "ceiling_anchor"
  | "efficient_producer"
  | "leverage_spike"
  | "baseline";

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
  // Only present when the trained multi-task heads served this player;
  // absent on older freezes (and always on rows from /history predating
  // the heads). Treat as progressive enhancement, never assume presence.
  pred_real_score_p10?: number;
  pred_real_score_p90?: number;
  archetype?: Archetype;
  streak_driver?: string;
  streak_quality?: number;
  stat_leverage?: number;
};

export type PayoutCurve = {
  regime: string;
  cash_line_percentile: number;
  percentile_to_payout: Record<string, number>;
};

export type ServingKnobs = {
  n_samples: number;
  n_field_lineups: number;
  top_n_filter: number;
  max_per_team: number;
  min_anchors: number;
  boost_sum_cap: number;
  max_single_boost: number;
  game_stack_bonus: number;
  leverage_weight: number;
  ceiling_weight: number;
  duplication_weight: number;
  field_same_game_boost: number;
  field_same_team_boost: number;
  duplication_aware_payout: boolean;
  never_skip: boolean;
  caveat_is_skip: boolean;
};

export type FrozenLineupPayload = {
  player_ids: number[];
  slot_multipliers: number[];
  lineup_score_p10: number;
  lineup_score_p50: number;
  lineup_score_p90: number;
  per_player?: PlayerProjection[];
  // Absent on freezes written before D90.
  payout_curve?: PayoutCurve;
  serving_knobs?: ServingKnobs;
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
  freeze_seq: number;
  frozen_via: string;
  // Only present on GET /lineup/{date} (a window-function column scoped
  // to that query); absent on rows from /lineup/{date}/history.
  n_freezes?: number;
};

// GET /lineup?limit=N -- one row per (slate_date, model_sha), latest freeze
// only. No per-player data and no `lineup` object at all: use
// fetchLineupHistory/fetchLatestLineup for anything past this summary.
export type SlateSummary = {
  slate_date: string;
  model_sha: string;
  payout_regime: string;
  frozen_at: string | null;
  entry_recommendation: "enter" | "skip" | "enter_with_caveat";
  expected_payout: number;
  freeze_seq: number;
  frozen_via: string;
};

export type WatchdogSeverity = "warn" | "error" | "critical";

export type WatchdogEvent = {
  trigger: string;
  severity: WatchdogSeverity;
  payload: unknown;
  created_at: string | null;
};

export type WatchdogToday = {
  slate_date: string;
  checked_at_utc: string;
  events: WatchdogEvent[];
  status: "ok" | WatchdogSeverity;
};

export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// Local (not UTC) slate date -- matches /lineup/{today} and
// /slate/{today}'s own concept of "today" so a browser near the UTC
// rollover doesn't see a different day than the API does. lib/espn.ts
// reuses this same value (reformatted) for its scoreboard query so both
// layers agree on the slate boundary.
export function localSlateDate(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

// ?demo=1/live/final returns a synthetic frozen lineup so the UI can be
// screenshotted or its live/final states exercised without a real slate.
// Defined inside the import.meta.env.DEV block so esbuild drops the
// whole fixture + lookup from production builds (verified: zero
// references to fixture players in the prod chunk).
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
    freeze_seq: 1,
    frozen_via: "job2",
    n_freezes: 1,
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
  if (getDemoMode() === null) return null;
  return getDemoFixture();
}

// Backs both fetchLatestLineup (today, no model_sha) and the depth pages
// that need an arbitrary past date (/slate/:date, /freezes/:date's diff
// base, /player/:date/:playerId). modelSha pins a specific frozen
// artifact per the API's optional ?model_sha= param; omit for "latest".
export async function fetchLineupForDate(
  date: string,
  modelSha?: string,
): Promise<FrozenLineup | null> {
  const qs = modelSha ? `?model_sha=${encodeURIComponent(modelSha)}` : "";
  const r = await fetch(`${API_URL}/lineup/${date}${qs}`);
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return (await r.json()) as FrozenLineup;
}

export async function fetchLatestLineup(): Promise<FrozenLineup | null> {
  const demo = demoFixture();
  if (demo) return demo;
  return fetchLineupForDate(localSlateDate());
}

// Slate timing for the pre-freeze countdown. freeze_target_utc is
// first_tip - freeze_lead_minutes (tip-relative T-40), so the loader clock
// tracks the real freeze instead of a hardcoded slot. 404 until job1 captures
// today's tip times, in which case the loader shows a neutral waiting caption.
export type SlateTiming = {
  slate_date: string;
  first_tip_utc: string | null;
  contest_lock_utc: string | null;
  freeze_lead_minutes: number;
  freeze_target_utc: string | null;
  picks_paused: boolean;
  resumes_on: string | null;
};

export async function fetchSlateTiming(): Promise<SlateTiming | null> {
  const today = localSlateDate();
  const r = await fetch(`${API_URL}/slate/${today}`);
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return (await r.json()) as SlateTiming;
}

// Every freeze appended for a slate, oldest first. 404 if the slate never
// froze at all.
export async function fetchLineupHistory(
  date: string,
): Promise<FrozenLineup[] | null> {
  const r = await fetch(`${API_URL}/lineup/${date}/history`);
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return (await r.json()) as FrozenLineup[];
}

// Most recent slates, newest first, one row per (slate, model). No
// per-player data -- see fetchLineupHistory for that.
export async function fetchRecentSlates(
  limit = 60,
): Promise<SlateSummary[]> {
  const r = await fetch(`${API_URL}/lineup?limit=${limit}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return (await r.json()) as SlateSummary[];
}

export async function fetchWatchdogToday(
  severityMin: WatchdogSeverity = "warn",
): Promise<WatchdogToday> {
  const r = await fetch(`${API_URL}/watchdog/today?severity_min=${severityMin}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return (await r.json()) as WatchdogToday;
}
