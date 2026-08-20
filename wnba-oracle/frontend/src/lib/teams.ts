// WNBA team code normalization and brand colors. per_player.team/opponent
// arrives from the Real Sports pool untranslated (whatever the platform's
// own key/abbreviation happens to be), and that has drifted before, so
// TO_ESPN accepts every alias we might receive and resolves it to the
// single ESPN scoreboard abbreviation used for joining live/final data
// and for color lookup. Team color is decorative only (rank gutter fill,
// headshot ring, hairline accent) -- never a text color.

export const TO_ESPN: Record<string, string> = {
  ATL: "ATL",
  CHI: "CHI",
  CON: "CON",
  CONN: "CON",
  DAL: "DAL",
  GSV: "GS",
  GVY: "GS",
  GS: "GS",
  IND: "IND",
  LVA: "LV",
  LV: "LV",
  LAS: "LA",
  LA: "LA",
  MIN: "MIN",
  NYL: "NY",
  NY: "NY",
  PDX: "POR",
  POR: "POR",
  PHO: "PHX",
  PHX: "PHX",
  SEA: "SEA",
  TOR: "TOR",
  WAS: "WSH",
  WSH: "WSH",
};

const ESPN_COLORS: Record<string, string> = {
  ATL: "#e31837",
  CHI: "#5091cd",
  CON: "#f05023",
  DAL: "#002b5c",
  GS: "#b38fcf",
  IND: "#002d62",
  LV: "#a7a8aa",
  LA: "#552583",
  MIN: "#266092",
  NY: "#86cebc",
  PHX: "#3c286e",
  POR: "#cee5eb",
  SEA: "#2c5235",
  TOR: "#33476d",
  WSH: "#e03a3e",
};

const FALLBACK = "var(--primary)";

export function espnCode(team: string | null | undefined): string | null {
  if (!team) return null;
  return TO_ESPN[team.toUpperCase().trim()] ?? null;
}

export function teamPrimary(team: string | null | undefined): string {
  const code = espnCode(team);
  if (!code) return FALLBACK;
  return ESPN_COLORS[code] ?? FALLBACK;
}
