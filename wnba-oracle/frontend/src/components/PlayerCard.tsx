// One pick. Mirrors the mlb-oracle layout: topbar (slot + boost),
// initials avatar in a team-color ring, FIRST / LAST identity, score
// block (Oracle Score = slot contribution, with raw P50), minutes
// interval bar, and a 3-cell detail rail.

import { useMemo } from "react";
import { BoostBadge } from "./BoostBadge";
import { Headshot } from "./Headshot";
import { IntervalBar } from "./IntervalBar";
import type { PlayerProjection } from "../lib/api";
import { teamPrimary } from "../lib/teamColors";

interface Props {
  rank: number;
  slotMultiplier: number;
  player: PlayerProjection;
}

function splitName(name: string): { first: string; last: string } {
  const trimmed = name.trim();
  if (!trimmed) return { first: "", last: "" };
  const parts = trimmed.split(/\s+/);
  if (parts.length === 1) return { first: "", last: parts[0] };
  const suffixRe = /^(?:Jr\.?|Sr\.?|II|III|IV)$/i;
  let last = parts[parts.length - 1];
  let firstEnd = parts.length - 1;
  if (suffixRe.test(last) && parts.length >= 2) {
    last = `${parts[parts.length - 2]} ${last}`;
    firstEnd = parts.length - 2;
  }
  const first = parts.slice(0, firstEnd).join(" ");
  return { first, last };
}

export function PlayerCard({ rank, slotMultiplier, player }: Props) {
  const { first, last } = useMemo(
    () => splitName(player.display_name),
    [player.display_name],
  );
  const teamColor = teamPrimary(player.team);
  const displayLast = last || first;
  const displayFirst = last ? first : "";

  const oracleScore = player.pred_real_score_p50 * (slotMultiplier || 1);
  const hasBoost = player.card_boost > 0;
  // Use the median minutes as the [min,max] domain anchor — the bar
  // shows the spread of predicted playing time. WNBA games cap around
  // 40 minutes; 0..40 is the conservative envelope.
  const minMin = 0;
  const maxMin = 40;

  return (
    <article
      className="card"
      style={{ ["--team-primary" as string]: teamColor }}
      aria-labelledby={`pick-${rank}-name`}
    >
      <div className="card__topbar">
        <span className="card__slot">
          <span className="card__slot-num">
            {String(rank).padStart(2, "0")}
          </span>
          <span>/&nbsp;05</span>
        </span>
        <div className="card__topbar-right">
          {hasBoost ? <BoostBadge cardBoost={player.card_boost} /> : null}
          <span className="pos-chip" aria-label={`Position: ${player.position}`}>
            {player.position}
          </span>
        </div>
      </div>

      <Headshot name={player.display_name} />

      <div className="identity">
        {displayFirst ? (
          <span className="identity__name-first">{displayFirst}</span>
        ) : null}
        <h2 className="identity__name" id={`pick-${rank}-name`}>
          {displayLast}
        </h2>
        <span className="identity__rule" aria-hidden="true" />
        <div className="identity__meta">
          <span>{player.team}</span>
          <span className="identity__meta-sep" aria-hidden="true" />
          <span>vs {player.opponent || "—"}</span>
        </div>
      </div>

      <div className="score" aria-label="Slot contribution and minutes interval">
        <div>
          <span className="score__label">Oracle Score</span>
          <span className="score__num">{oracleScore.toFixed(1)}</span>
        </div>
        <div className="score__rhs">
          <span className="score__rhs-label">Raw P50</span>
          <span className="score__rhs-val">
            {player.pred_real_score_p50.toFixed(2)}
          </span>
        </div>
        <div className="score__interval">
          <IntervalBar
            p10={player.pred_minutes_p10}
            p50={player.pred_minutes_p50}
            p90={player.pred_minutes_p90}
            min={minMin}
            max={maxMin}
            unit="m"
            ariaLabel={`Predicted minutes: P10 ${player.pred_minutes_p10.toFixed(0)}, median ${player.pred_minutes_p50.toFixed(0)}, P90 ${player.pred_minutes_p90.toFixed(0)}.`}
          />
        </div>
      </div>

      <div className="detail-rail" aria-label="Pick provenance">
        <div className="detail-rail__cell">
          <span className="detail-rail__label">Slot mult</span>
          <span className="detail-rail__val">
            ×{slotMultiplier.toFixed(2)}
          </span>
          <span className="detail-rail__sub">optimizer weight</span>
        </div>
        <div className="detail-rail__cell">
          <span className="detail-rail__label">Card boost</span>
          <span className="detail-rail__val">
            {hasBoost ? `+${player.card_boost.toFixed(2)}x` : "—"}
          </span>
          <span className="detail-rail__sub">platform bonus</span>
        </div>
        <div className="detail-rail__cell">
          <span className="detail-rail__label">Min P10–P90</span>
          <span className="detail-rail__val">
            {player.pred_minutes_p10.toFixed(0)}–
            {player.pred_minutes_p90.toFixed(0)}
          </span>
          <span className="detail-rail__sub">minutes range</span>
        </div>
      </div>
    </article>
  );
}
