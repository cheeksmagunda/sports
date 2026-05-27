// WNBA team primary colors. Used to tint the player card halo + name and
// the headshot ring. Falls back to the brand teal when the team string is
// unknown (preseason teams, abbreviation drift).

const COLORS: Record<string, string> = {
  ATL: "#C8102E", // Dream
  CHI: "#418FDE", // Sky
  CON: "#0A2240", // Sun
  DAL: "#0C2340", // Wings
  IND: "#FFCD00", // Fever
  LVA: "#000000", // Aces
  LV:  "#000000",
  LAS: "#552583", // Sparks
  LA:  "#552583",
  MIN: "#236192", // Lynx
  NYL: "#6ECEB2", // Liberty
  NY:  "#6ECEB2",
  PHO: "#201747", // Mercury
  PHX: "#201747",
  SEA: "#2C5234", // Storm
  WAS: "#002B5C", // Mystics
  WSH: "#002B5C",
  GVY: "#FF6900", // Valkyries (placeholder)
  GSV: "#FF6900",
};

const FALLBACK = "var(--primary)";

export function teamPrimary(team: string | null | undefined): string {
  if (!team) return FALLBACK;
  const key = team.toUpperCase().trim();
  return COLORS[key] ?? FALLBACK;
}
