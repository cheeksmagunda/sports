// Central ?demo= reader, dev-only (see api.ts's demoFixture for why: the
// whole point is esbuild drops this from production builds). Recognizes
// the full named-state matrix (prefreeze, frozen, live, final, paused,
// noslate, error, refrozen); "1" is the legacy default-lineup fixture.
// Phase 6: used for E2E no-scroll gate and comprehensive state testing.

export type DemoMode =
  | "1"
  | "prefreeze"
  | "frozen"
  | "live"
  | "final"
  | "paused"
  | "noslate"
  | "error"
  | "refrozen"
  | null;

export function getDemoMode(): DemoMode {
  if (!import.meta.env.DEV) return null;
  if (typeof window === "undefined") return null;
  const v = new URLSearchParams(window.location.search).get("demo");
  const valid: DemoMode[] = ["1", "prefreeze", "frozen", "live", "final", "paused", "noslate", "error", "refrozen"];
  if (valid.includes(v as DemoMode)) return v as DemoMode;
  return null;
}
