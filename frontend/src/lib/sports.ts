export const SPORTS = [
  { id: "nfl", label: "NFL" },
  { id: "nba", label: "NBA" },
  { id: "nhl", label: "NHL" },
] as const;

export type SportId = (typeof SPORTS)[number]["id"];

export function isSportId(value: string | undefined): value is SportId {
  return SPORTS.some((sport) => sport.id === value);
}
