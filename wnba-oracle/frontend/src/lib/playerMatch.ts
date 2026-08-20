// Joins our players onto ESPN's by normalized name within the same
// team, since there's no shared id. Matching within one ESPN team block
// narrows candidates to about twelve people, making collisions very
// unlikely. Never throws; a miss returns null and the caller degrades
// (full prediction display stays, initials fallback, a neutral
// "no live data" marker) -- never blank a row, never block the total.

import type { PlayerProjection } from "./api";
import type { PlayerBoxLine } from "./espn";
import { espnCode } from "./teams";

const CACHE_KEY = "wnba-oracle.athlete-ids.v1";

function normalizeName(name: string): string {
  return name
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .replace(/[.']/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase()
    .replace(/\s+(jr|sr|ii|iii|iv)$/i, "");
}

function cacheKey(displayName: string, team: string): string {
  return `${normalizeName(displayName)}|${(espnCode(team) ?? team).toLowerCase()}`;
}

function loadCache(): Record<string, string> {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveCache(cache: Record<string, string>): void {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(cache));
  } catch {
    // Storage full or unavailable (private browsing) -- matching just
    // re-runs next call, no functional loss.
  }
}

// Resolves a served player to an ESPN athlete id by matching within the
// same ESPN-mapped team's box lines, caching the result. boxLines should
// be every relevant game's lines pooled together; filtering by team
// narrows to the right game implicitly.
export function resolveAthleteId(
  displayName: string,
  team: string,
  boxLines: PlayerBoxLine[],
): string | null {
  const key = cacheKey(displayName, team);
  const cache = loadCache();
  if (cache[key]) return cache[key];

  const teamCode = espnCode(team);
  const targetName = normalizeName(displayName);
  const candidates = teamCode ? boxLines.filter((b) => b.team === teamCode) : boxLines;
  const match = candidates.find((b) => normalizeName(b.displayName) === targetName);
  if (!match) return null;

  cache[key] = match.espnAthleteId;
  saveCache(cache);
  return match.espnAthleteId;
}

export function resolveBoxLine(
  displayName: string,
  team: string,
  boxLines: PlayerBoxLine[],
): PlayerBoxLine | null {
  const id = resolveAthleteId(displayName, team, boxLines);
  if (!id) return null;
  return boxLines.find((b) => b.espnAthleteId === id) ?? null;
}

export type CombinedBoxLine = {
  points: number;
  rebounds: number;
  assists: number;
  steals: number;
  blocks: number;
  turnovers: number;
  minutes: number;
  matchedCount: number;
};

// Sums reported stats across whichever of the five actually matched.
// Unmatched players simply don't contribute -- never blocks the total.
export function combineBoxLines(
  players: PlayerProjection[],
  boxLines: PlayerBoxLine[],
): CombinedBoxLine {
  const totals: CombinedBoxLine = {
    points: 0,
    rebounds: 0,
    assists: 0,
    steals: 0,
    blocks: 0,
    turnovers: 0,
    minutes: 0,
    matchedCount: 0,
  };
  for (const p of players) {
    const line = resolveBoxLine(p.display_name, p.team, boxLines);
    if (!line) continue;
    totals.points += line.points ?? 0;
    totals.rebounds += line.rebounds ?? 0;
    totals.assists += line.assists ?? 0;
    totals.steals += line.steals ?? 0;
    totals.blocks += line.blocks ?? 0;
    totals.turnovers += line.turnovers ?? 0;
    totals.minutes += line.minutes ?? 0;
    totals.matchedCount += 1;
  }
  return totals;
}
