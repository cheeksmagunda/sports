import type { FrozenLineup } from "./api";

type EntryRecommendation = FrozenLineup["entry_recommendation"];

export type RecommendationActionabilityReason =
  | "current"
  | "stale_lineup"
  | "not_today"
  | "non_production_freeze"
  | "paused"
  | "unknown_lock"
  | "locked"
  | "invalid_freeze_time";

export interface RecommendationActionabilityInput {
  recommendation: EntryRecommendation;
  lineupSlateDate: string;
  timingSlateDate: string | null;
  todaySlateDate: string;
  frozenAtUtc: string;
  frozenVia: string;
  lineupFresh: boolean;
  picksPaused: boolean;
  firstTipUtc: string | null;
  contestLockUtc: string | null;
  nowMs: number;
}

export interface RecommendationActionability {
  actionable: boolean;
  label: string;
  reason: RecommendationActionabilityReason;
  effectiveLockUtc: string | null;
}

const PRODUCTION_FREEZE_PATHS = new Set([
  "job2_first_fire",
  "job2_late_refreeze",
]);

const RECOMMENDATION_LABEL: Record<EntryRecommendation, string> = {
  enter: "Enter",
  enter_with_caveat: "Enter · Caveat",
  skip: "Skip",
};

/**
 * The contest lock is authoritative when supplied. A malformed contest lock
 * must not silently fall back to first tip, because that could extend the
 * apparent entry window beyond the provider's actual lock.
 */
export function effectiveLockUtc(
  contestLockUtc: string | null,
  firstTipUtc: string | null,
): string | null {
  return contestLockUtc ?? firstTipUtc;
}

function nonActionable(
  recommendation: EntryRecommendation,
  reason: Exclude<RecommendationActionabilityReason, "current">,
  lockUtc: string | null,
): RecommendationActionability {
  return {
    actionable: false,
    label: `Frozen call: ${RECOMMENDATION_LABEL[recommendation]}`,
    reason,
    effectiveLockUtc: lockUtc,
  };
}

/**
 * Turns a model call into imperative UI copy only when every serving boundary
 * proves that the call can still be acted on. Unknown or contradictory state
 * intentionally degrades to a recorded, non-actionable call.
 */
export function getRecommendationActionability(
  input: RecommendationActionabilityInput,
): RecommendationActionability {
  const lockUtc = effectiveLockUtc(input.contestLockUtc, input.firstTipUtc);

  if (!input.lineupFresh) {
    return nonActionable(input.recommendation, "stale_lineup", lockUtc);
  }
  if (
    input.lineupSlateDate !== input.todaySlateDate ||
    input.timingSlateDate !== input.todaySlateDate
  ) {
    return nonActionable(input.recommendation, "not_today", lockUtc);
  }
  if (!PRODUCTION_FREEZE_PATHS.has(input.frozenVia)) {
    return nonActionable(input.recommendation, "non_production_freeze", lockUtc);
  }
  if (input.picksPaused) {
    return nonActionable(input.recommendation, "paused", lockUtc);
  }
  if (!lockUtc) {
    return nonActionable(input.recommendation, "unknown_lock", null);
  }

  const lockMs = Date.parse(lockUtc);
  if (Number.isNaN(lockMs)) {
    return nonActionable(input.recommendation, "unknown_lock", lockUtc);
  }
  if (input.nowMs >= lockMs) {
    return nonActionable(input.recommendation, "locked", lockUtc);
  }

  const frozenAtMs = Date.parse(input.frozenAtUtc);
  if (
    Number.isNaN(frozenAtMs) ||
    frozenAtMs > input.nowMs ||
    frozenAtMs >= lockMs
  ) {
    return nonActionable(input.recommendation, "invalid_freeze_time", lockUtc);
  }

  return {
    actionable: true,
    label:
      input.recommendation === "enter"
        ? "Enter now"
        : input.recommendation === "enter_with_caveat"
          ? "Enter now · Caveat"
          : RECOMMENDATION_LABEL.skip,
    reason: "current",
    effectiveLockUtc: lockUtc,
  };
}
