// ESPN scoreboard + summary access, normalized to a small internal shape
// so ESPN's response structure never leaks into components. Enrichment
// only: every failure here must degrade (empty array / null), never
// throw into a render path, and never touch web.realapp.com (auth-gated,
// bot-blocked, and AGENTS.md forbids it from the browser entirely).

import { getDemoMode } from "./demo";

const ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba";

export type GameState = "pre" | "in" | "post";

export type ScoreboardGame = {
  eventId: string;
  tipUtc: string;
  shortName: string;
  state: GameState;
  statusDescription: string;
  completed: boolean;
  period: number;
  displayClock: string;
  home: { team: string; score: number };
  away: { team: string; score: number };
};

export type PlayerBoxLine = {
  espnAthleteId: string;
  displayName: string;
  team: string;
  starter: boolean;
  didNotPlay: boolean;
  dnpReason: string | null;
  minutes: number | null;
  points: number | null;
  rebounds: number | null;
  assists: number | null;
  turnovers: number | null;
  steals: number | null;
  blocks: number | null;
  fgMade: number | null;
  fgAttempted: number | null;
};

// "YYYY-MM-DD" -> "YYYYMMDD" for the scoreboard's ?dates= param. Callers
// pass the same local slate date used for /lineup/{date} and
// /slate/{date} (api.ts's localSlateDate) so ESPN's day boundary matches
// ours instead of drifting across the UTC rollover.
export function toEspnDate(isoDate: string): string {
  return isoDate.replaceAll("-", "");
}

interface EspnCompetitor {
  homeAway?: string;
  team?: { abbreviation?: string };
  score?: string | number;
}

interface EspnEvent {
  id?: string | number;
  date?: string;
  shortName?: string;
  status?: {
    type?: { state?: string; description?: string; completed?: boolean };
    period?: number;
    displayClock?: string;
  };
  competitions?: Array<{ competitors?: EspnCompetitor[] }>;
}

interface EspnAthleteEntry {
  athlete?: { id?: string | number; displayName?: string };
  starter?: boolean;
  didNotPlay?: boolean;
  reason?: string;
  stats?: string[];
}

interface EspnPlayerGroup {
  team?: { abbreviation?: string };
  statistics?: Array<{ names?: string[]; athletes?: EspnAthleteEntry[] }>;
}

function normalizeGame(event: unknown): ScoreboardGame | null {
  try {
    const e = event as EspnEvent;
    const competition = e.competitions?.[0];
    const competitors: EspnCompetitor[] = competition?.competitors ?? [];
    const home = competitors.find((c) => c.homeAway === "home");
    const away = competitors.find((c) => c.homeAway === "away");
    if (!home || !away || !e.id) return null;
    return {
      eventId: String(e.id),
      tipUtc: e.date ?? "",
      shortName: e.shortName ?? "",
      state: (e.status?.type?.state as GameState) ?? "pre",
      statusDescription: e.status?.type?.description ?? "",
      completed: Boolean(e.status?.type?.completed),
      period: Number(e.status?.period ?? 0),
      displayClock: e.status?.displayClock ?? "",
      home: { team: home.team?.abbreviation ?? "", score: Number(home.score ?? 0) },
      away: { team: away.team?.abbreviation ?? "", score: Number(away.score ?? 0) },
    };
  } catch {
    return null;
  }
}

export async function fetchScoreboard(dateYyyymmdd: string): Promise<ScoreboardGame[]> {
  const demo = getDemoMode();
  if (demo === "live" && getDemoGames) return getDemoGames("live");
  if (demo === "final" && getDemoGames) return getDemoGames("final");

  const r = await fetch(`${ESPN_BASE}/scoreboard?dates=${dateYyyymmdd}`);
  if (!r.ok) throw new Error(`ESPN scoreboard HTTP ${r.status}`);
  const data = await r.json();
  const events: unknown[] = Array.isArray(data?.events) ? data.events : [];
  return events.map(normalizeGame).filter((g): g is ScoreboardGame => g !== null);
}

function statValue(names: string[], values: string[], name: string): string | undefined {
  const idx = names.indexOf(name);
  return idx === -1 ? undefined : values[idx];
}

function toNum(raw: string | undefined): number | null {
  if (raw === undefined || raw === "") return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

function parseMadeAttempted(raw: string | undefined): { made: number | null; attempted: number | null } {
  if (!raw) return { made: null, attempted: null };
  const [made, attempted] = raw.split("-");
  return { made: toNum(made), attempted: toNum(attempted) };
}

function normalizePlayerLine(athleteEntry: unknown, names: string[], team: string): PlayerBoxLine | null {
  try {
    const a = athleteEntry as EspnAthleteEntry;
    const athlete = a.athlete;
    if (!athlete?.id) return null;
    const values: string[] = Array.isArray(a.stats) ? a.stats : [];
    const fg = parseMadeAttempted(statValue(names, values, "FG"));
    return {
      espnAthleteId: String(athlete.id),
      displayName: athlete.displayName ?? "",
      team,
      starter: Boolean(a.starter),
      didNotPlay: Boolean(a.didNotPlay),
      dnpReason: a.reason ?? null,
      minutes: toNum(statValue(names, values, "MIN")),
      points: toNum(statValue(names, values, "PTS")),
      rebounds: toNum(statValue(names, values, "REB")),
      assists: toNum(statValue(names, values, "AST")),
      turnovers: toNum(statValue(names, values, "TO")),
      steals: toNum(statValue(names, values, "STL")),
      blocks: toNum(statValue(names, values, "BLK")),
      fgMade: fg.made,
      fgAttempted: fg.attempted,
    };
  } catch {
    return null;
  }
}

export async function fetchSummary(eventId: string): Promise<PlayerBoxLine[]> {
  const demo = getDemoMode();
  if ((demo === "live" || demo === "final") && getDemoBoxLines) {
    return getDemoBoxLines(eventId);
  }

  const r = await fetch(`${ESPN_BASE}/summary?event=${eventId}`);
  if (!r.ok) throw new Error(`ESPN summary HTTP ${r.status}`);
  const data = await r.json();
  const groups: unknown[] = Array.isArray(data?.boxscore?.players) ? data.boxscore.players : [];
  const out: PlayerBoxLine[] = [];
  for (const group of groups) {
    const g = group as EspnPlayerGroup;
    const teamAbbr = g.team?.abbreviation ?? "";
    const stats = g.statistics?.[0];
    const names: string[] = Array.isArray(stats?.names) ? stats.names : [];
    const athletes: unknown[] = Array.isArray(stats?.athletes) ? stats.athletes : [];
    for (const entry of athletes) {
      const line = normalizePlayerLine(entry, names, teamAbbr);
      if (line) out.push(line);
    }
  }
  return out;
}

// ── Demo fixtures (?demo=live / ?demo=final). Defined inside the
// import.meta.env.DEV block, same pattern as api.ts's demo lineup, so
// esbuild drops all of it (including the "A'ja Wilson" etc. literals)
// from production builds -- a runtime getDemoMode() check alone isn't
// enough for the bundler to prove this code is unreachable in prod.
// Mirrors api.ts's demo lineup (Wilson/Stewart/Ionescu/Clark/Collier) so
// the two demo layers join correctly. Sabrina Ionescu is deliberately
// left out of the box lines to exercise the unmatched-player
// degradation path Phase 3's acceptance criteria call for.
let getDemoGames: ((mode: "live" | "final") => ScoreboardGame[]) | null = null;
let getDemoBoxLines: ((eventId: string) => PlayerBoxLine[]) | null = null;

if (import.meta.env.DEV) {
  const DEMO_EVENT_LV_NY = "demo-lv-ny";
  const DEMO_EVENT_IND_CHI = "demo-ind-chi";
  const DEMO_EVENT_MIN_SEA = "demo-min-sea";

  const demoGame = (
    eventId: string,
    home: string,
    away: string,
    state: GameState,
    homeScore: number,
    awayScore: number,
  ): ScoreboardGame => ({
    eventId,
    tipUtc: new Date(0).toISOString(),
    shortName: `${away} @ ${home}`,
    state,
    statusDescription: state === "post" ? "Final" : state === "in" ? "In Progress" : "Scheduled",
    completed: state === "post",
    period: state === "pre" ? 0 : 4,
    displayClock: state === "post" ? "0.0" : "5:12",
    home: { team: home, score: homeScore },
    away: { team: away, score: awayScore },
  });

  getDemoGames = (mode) => {
    if (mode === "final") {
      return [
        demoGame(DEMO_EVENT_LV_NY, "NY", "LV", "post", 90, 96),
        demoGame(DEMO_EVENT_IND_CHI, "CHI", "IND", "post", 80, 88),
        demoGame(DEMO_EVENT_MIN_SEA, "SEA", "MIN", "post", 88, 91),
      ];
    }
    return [
      demoGame(DEMO_EVENT_LV_NY, "NY", "LV", "in", 78, 82),
      demoGame(DEMO_EVENT_IND_CHI, "CHI", "IND", "in", 64, 70),
      demoGame(DEMO_EVENT_MIN_SEA, "SEA", "MIN", "post", 88, 91),
    ];
  };

  const demoBoxLine = (
    id: string,
    name: string,
    team: string,
    overrides: Partial<PlayerBoxLine> = {},
  ): PlayerBoxLine => ({
    espnAthleteId: id,
    displayName: name,
    team,
    starter: true,
    didNotPlay: false,
    dnpReason: null,
    minutes: 24,
    points: 18,
    rebounds: 6,
    assists: 4,
    turnovers: 2,
    steals: 1,
    blocks: 0,
    fgMade: 7,
    fgAttempted: 14,
    ...overrides,
  });

  const DEMO_BOX_LINES: Record<string, PlayerBoxLine[]> = {
    [DEMO_EVENT_LV_NY]: [
      demoBoxLine("d1", "A'ja Wilson", "LV", { points: 24, rebounds: 9, assists: 3, minutes: 31 }),
      demoBoxLine("d2", "Breanna Stewart", "NY", { points: 21, rebounds: 8, assists: 5, minutes: 33 }),
    ],
    [DEMO_EVENT_IND_CHI]: [
      demoBoxLine("d4", "Caitlin Clark", "IND", { points: 19, rebounds: 5, assists: 8, minutes: 30 }),
    ],
    [DEMO_EVENT_MIN_SEA]: [
      demoBoxLine("d5", "Napheesa Collier", "MIN", { points: 22, rebounds: 10, assists: 2, minutes: 29 }),
    ],
  };

  getDemoBoxLines = (eventId) => DEMO_BOX_LINES[eventId] ?? [];
}
