// Hero strip beneath the header. Title + three live stats derived from
// the lineup payload. Entry recommendation surfaces as a chip.

import type { FrozenLineup } from "../lib/api";

interface Props {
  lineup: FrozenLineup;
}

const REC_LABEL: Record<string, string> = {
  enter: "Enter",
  enter_with_caveat: "Enter · Caveat",
  skip: "Skip",
};

export function SlateBand({ lineup }: Props) {
  const players = lineup.lineup.per_player ?? [];
  const boosted = players.filter((p) => p.card_boost > 0).length;
  const median = lineup.lineup.lineup_score_p50;
  const ev = lineup.expected_payout;
  const rec = lineup.entry_recommendation;
  const recLabel = REC_LABEL[rec] ?? rec.replaceAll("_", " ");

  return (
    <section className="slate-band" aria-label="Slate summary">
      <div className="slate-band__title-row">
        <span className="slate-band__caption">
          Today&rsquo;s five &middot; frozen for the day
        </span>
        <h1 className="slate-band__title">
          The Five<em>.</em>
        </h1>
        <span
          className={`slate-band__chip slate-band__chip--${rec}`}
          aria-label={`Entry recommendation: ${recLabel}`}
        >
          {recLabel}
        </span>
      </div>
      <div className="slate-band__right" aria-hidden="false">
        <div>
          <span className="slate-band__stat-label">Lineup P50</span>
          <span className="slate-band__stat-val">{median.toFixed(1)}</span>
        </div>
        <span className="slate-band__divider" />
        <div>
          <span className="slate-band__stat-label">Boosted</span>
          <span className="slate-band__stat-val">{boosted} / 5</span>
        </div>
        <span className="slate-band__divider" />
        <div>
          <span className="slate-band__stat-label">EV</span>
          <span className="slate-band__stat-val">{ev.toFixed(2)}</span>
        </div>
      </div>
    </section>
  );
}
