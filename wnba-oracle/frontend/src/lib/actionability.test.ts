import { describe, expect, it } from "vitest";
import {
  effectiveLockUtc,
  getRecommendationActionability,
  type RecommendationActionabilityInput,
} from "./actionability";

const NOW = Date.parse("2026-08-22T22:00:00Z");

function currentInput(
  overrides: Partial<RecommendationActionabilityInput> = {},
): RecommendationActionabilityInput {
  return {
    recommendation: "enter",
    lineupSlateDate: "2026-08-22",
    timingSlateDate: "2026-08-22",
    todaySlateDate: "2026-08-22",
    frozenAtUtc: "2026-08-22T21:55:00Z",
    frozenVia: "job2_first_fire",
    lineupFresh: true,
    picksPaused: false,
    firstTipUtc: "2026-08-22T23:00:00Z",
    contestLockUtc: "2026-08-22T22:20:00Z",
    nowMs: NOW,
    ...overrides,
  };
}

describe("effectiveLockUtc", () => {
  it("prefers contest lock over first tip", () => {
    expect(
      effectiveLockUtc("2026-08-22T22:20:00Z", "2026-08-22T23:00:00Z"),
    ).toBe("2026-08-22T22:20:00Z");
  });

  it("falls back to first tip only when contest lock is absent", () => {
    expect(effectiveLockUtc(null, "2026-08-22T23:00:00Z")).toBe(
      "2026-08-22T23:00:00Z",
    );
    expect(effectiveLockUtc("bad-lock", "2026-08-22T23:00:00Z")).toBe(
      "bad-lock",
    );
  });
});

describe("getRecommendationActionability", () => {
  it("uses imperative entry copy only for a fresh current production call before lock", () => {
    expect(getRecommendationActionability(currentInput())).toEqual({
      actionable: true,
      label: "Enter now",
      reason: "current",
      effectiveLockUtc: "2026-08-22T22:20:00Z",
    });
  });

  it("allows a current late refreeze and formats caveat copy", () => {
    const result = getRecommendationActionability(
      currentInput({
        recommendation: "enter_with_caveat",
        frozenVia: "job2_late_refreeze",
      }),
    );

    expect(result.actionable).toBe(true);
    expect(result.label).toBe("Enter now · Caveat");
  });

  it("uses first tip as the effective lock when contest lock is absent", () => {
    const result = getRecommendationActionability(
      currentInput({ contestLockUtc: null }),
    );

    expect(result.actionable).toBe(true);
    expect(result.effectiveLockUtc).toBe("2026-08-22T23:00:00Z");
  });

  it("fails closed exactly at and after lock", () => {
    for (const nowMs of [
      Date.parse("2026-08-22T22:20:00Z"),
      Date.parse("2026-08-22T22:20:00.001Z"),
    ]) {
      expect(getRecommendationActionability(currentInput({ nowMs }))).toMatchObject({
        actionable: false,
        label: "Frozen call: Enter",
        reason: "locked",
      });
    }
  });

  it("fails closed when lock timing is absent or invalid", () => {
    for (const overrides of [
      { contestLockUtc: null, firstTipUtc: null },
      { contestLockUtc: "not-a-date" },
    ]) {
      expect(
        getRecommendationActionability(currentInput(overrides)),
      ).toMatchObject({
        actionable: false,
        label: "Frozen call: Enter",
        reason: "unknown_lock",
      });
    }
  });

  it("fails closed for stale, historical, paused, and non-production calls", () => {
    const cases: Array<[
      Partial<RecommendationActionabilityInput>,
      string,
    ]> = [
      [{ lineupFresh: false }, "stale_lineup"],
      [{ lineupSlateDate: "2026-08-21" }, "not_today"],
      [{ timingSlateDate: null }, "not_today"],
      [{ picksPaused: true }, "paused"],
      [{ frozenVia: "job2_upcoming_games_only" }, "non_production_freeze"],
      [{ frozenVia: "job2" }, "non_production_freeze"],
    ];

    for (const [overrides, reason] of cases) {
      expect(
        getRecommendationActionability(currentInput(overrides)),
      ).toMatchObject({
        actionable: false,
        label: "Frozen call: Enter",
        reason,
      });
    }
  });

  it("fails closed when freeze provenance time is contradictory", () => {
    for (const frozenAtUtc of [
      "not-a-date",
      "2026-08-22T22:05:00Z",
      "2026-08-22T22:20:00Z",
    ]) {
      expect(
        getRecommendationActionability(currentInput({ frozenAtUtc })),
      ).toMatchObject({
        actionable: false,
        label: "Frozen call: Enter",
        reason: "invalid_freeze_time",
      });
    }
  });

  it("uses recorded wording for a non-actionable skip", () => {
    expect(
      getRecommendationActionability(
        currentInput({
          recommendation: "skip",
          lineupSlateDate: "2026-08-21",
        }),
      ),
    ).toMatchObject({
      actionable: false,
      label: "Frozen call: Skip",
    });
  });
});
