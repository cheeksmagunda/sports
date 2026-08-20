// Central ?demo= reader, dev-only (see api.ts's demoFixture for why: the
// whole point is esbuild drops this from production builds). Phase 6
// expands this to the full named-state matrix (prefreeze, frozen, live,
// final, paused, noslate, error, refrozen); for now it recognizes "1"
// (the original default-lineup fixture) plus "live" and "final", pulled
// forward from Phase 6 because Phase 3's own acceptance criteria need
// them to demo the ESPN-sourced states.

export type DemoMode = "1" | "live" | "final" | null;

export function getDemoMode(): DemoMode {
  if (!import.meta.env.DEV) return null;
  if (typeof window === "undefined") return null;
  const v = new URLSearchParams(window.location.search).get("demo");
  if (v === "1" || v === "live" || v === "final") return v;
  return null;
}
