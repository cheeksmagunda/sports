// Hero strip beneath the header. Always renders (row 2 of the app grid)
// so the shell's row count never shifts; renders a neutral title-only
// state when there's no lineup yet. Pre-tip shows the projected total
// and provenance; live/final show the actual reported combined stat
// line instead, with the projection kept only as a static reference
// range -- never labeled as a live estimate.

import { Link } from "react-router-dom";
import type { FrozenLineup } from "../lib/api";
import type { SlateLifecycleState } from "../hooks/useSlateLifecycle";
import type { RecommendationActionability } from "../lib/actionability";
import type { CombinedBoxLine } from "../lib/playerMatch";

interface Props {
  lineup: FrozenLineup | null;
  lifecycleState?: SlateLifecycleState;
  combined?: CombinedBoxLine;
  gamesRemaining?: number;
  recommendationActionability?: RecommendationActionability;
}

const REC_LABEL: Record<string, string> = {
  enter: "Enter",
  enter_with_caveat: "Enter · Caveat",
  skip: "Skip",
};

export function SlateBand({
  lineup,
  lifecycleState,
  combined,
  gamesRemaining,
  recommendationActionability,
}: Props) {
  if (!lineup) {
    return (
      <section className="slate-band" aria-label="Slate summary">
        <div className="slate-band__title-row">
          <span className="slate-band__caption">Today&rsquo;s five</span>
          <h1 className="slate-band__title">
            The Five<em>.</em>
          </h1>
        </div>
      </section>
    );
  }

  const rec = lineup.entry_recommendation;
  const recordedLabel = REC_LABEL[rec] ?? rec.replaceAll("_", " ");
  const recLabel =
    recommendationActionability?.label ?? `Frozen call: ${recordedLabel}`;
  const recIsActionable = recommendationActionability?.actionable ?? false;
  const { lineup_score_p10: p10, lineup_score_p50: p50, lineup_score_p90: p90 } =
    lineup.lineup;
  const nFreezes = lineup.n_freezes ?? 1;
  const showFreezeChip = nFreezes > 1;
  const isLiveOrFinal = lifecycleState === "live" || lifecycleState === "final";

  return (
    <section className="slate-band" aria-label="Slate summary">
      <div className="slate-band__title-row">
        <span className="slate-band__caption">
          {isLiveOrFinal
            ? lifecycleState === "final"
              ? "Today's five · final"
              : "Today's five · live"
            : "Today's five · frozen for the day"}
        </span>
        <h1 className="slate-band__title">
          The Five<em>.</em>
        </h1>
        <div className="slate-band__chips">
          <span
            className={`slate-band__chip slate-band__chip--${rec}`}
            aria-label={`${recIsActionable ? "Current" : "Recorded"} entry recommendation: ${recLabel}`}
          >
            {recLabel}
          </span>
          {showFreezeChip ? (
            <Link
              to={`/freezes/${lineup.slate_date}`}
              className="slate-band__chip slate-band__chip--freeze"
            >
              Freeze {lineup.freeze_seq} of {nFreezes}
            </Link>
          ) : null}
        </div>
      </div>

      {isLiveOrFinal && combined ? (
        <div className="slate-band__right" aria-hidden="false">
          <div>
            <span className="slate-band__stat-label">Combined</span>
            <span className="slate-band__stat-val slate-band__stat-val--flanked">
              <span className="slate-band__stat-flank">
                {combined.rebounds}r {combined.assists}a
              </span>
              {combined.points}p
              <span className="slate-band__stat-flank">
                {combined.steals}s {combined.blocks}b {combined.turnovers}to
              </span>
            </span>
          </div>
          <span className="slate-band__divider" />
          <div>
            <span className="slate-band__stat-label">Projected (reference)</span>
            <span className="slate-band__stat-val slate-band__stat-val--flanked">
              <span className="slate-band__stat-flank">{p10.toFixed(0)}</span>
              {p50.toFixed(1)}
              <span className="slate-band__stat-flank">{p90.toFixed(0)}</span>
            </span>
          </div>
          {typeof gamesRemaining === "number" ? (
            <>
              <span className="slate-band__divider" />
              <div>
                <span className="slate-band__stat-label">Games remaining</span>
                <span className="slate-band__stat-val">{gamesRemaining}</span>
              </div>
            </>
          ) : null}
        </div>
      ) : (
        <div className="slate-band__right" aria-hidden="false">
          <div>
            <span className="slate-band__stat-label">Projected</span>
            <span className="slate-band__stat-val slate-band__stat-val--flanked">
              <span className="slate-band__stat-flank">{p10.toFixed(0)}</span>
              {p50.toFixed(1)}
              <span className="slate-band__stat-flank">{p90.toFixed(0)}</span>
            </span>
          </div>
          <span className="slate-band__divider" />
          <div>
            <span className="slate-band__stat-label">Expected payout</span>
            <span className="slate-band__stat-val">
              {lineup.expected_payout.toFixed(2)}
            </span>
          </div>
        </div>
      )}
    </section>
  );
}
