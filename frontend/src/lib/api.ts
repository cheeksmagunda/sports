import type { SportId } from "./sports";

const TIMEOUT_MS = 10_000;

export type Health = { status: string; [key: string]: unknown };

export type Pick = {
  slot?: number;
  name: string;
  team?: string;
  opponent?: string | null;
  position?: string;
  slot_multiplier?: number;
  projected_value?: number;
  card_boost?: number;
};

export type LineupPayload = {
  status?: string;
  slate_date?: string;
  date?: string;
  frozen_at?: string | null;
  cutoff_at?: string | null;
  boost_regime?: string | null;
  lineup?: { picks?: Pick[] } | null;
  [key: string]: unknown;
};

/** Central time date, the slate day used by the NFL app. */
export function centralDate(now = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Chicago",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(now);
}

async function getJson<T>(sport: SportId, path: string): Promise<T | null> {
  const controller = new AbortController();
  const timer = globalThis.setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(`/api/${sport}${path}`, {
      cache: "no-store",
      signal: controller.signal,
    });
    if (response.status === 404) return null;
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return (await response.json()) as T;
  } catch (error) {
    if (controller.signal.aborted) throw new Error("Request timed out", { cause: error });
    throw error;
  } finally {
    globalThis.clearTimeout(timer);
  }
}

export const fetchHealth = (sport: SportId) => getJson<Health>(sport, "/health");

export const fetchLineup = (sport: SportId, day: string) =>
  getJson<LineupPayload>(sport, `/lineup/${encodeURIComponent(day)}`);

/** Picks only when the payload carries a well-formed list; otherwise none. */
export function picksOf(payload: LineupPayload | null): Pick[] {
  const picks = payload?.lineup?.picks;
  return Array.isArray(picks) ? picks.filter((p) => typeof p?.name === "string") : [];
}
