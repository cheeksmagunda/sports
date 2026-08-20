// One row of the Slip. Rank is the layout spine: a full-bleed team-color
// gutter with a huge numeral, not a small chip. Desktop shows all six
// regions (rank, identity, slot, projection, minutes, live); a container
// query (not a viewport media query, so this same component ports to
// /slate/:date unchanged) collapses slot into the identity meta line and
// merges projection+minutes into one block on narrow rows. The live
// region is a placeholder until Phase 3 wires ESPN box scores.

import { Link } from "react-router-dom";
import type { PlayerProjection } from "../lib/api";
import { teamInk, teamPrimary } from "../lib/teams";
import { BoostBadge } from "./BoostBadge";
import { Headshot } from "./Headshot";
import { IntervalBar } from "./IntervalBar";

interface Props {
  rank: number;
  slotMultiplier: number;
  player: PlayerProjection;
  slateDate: string;
}

function clamp01(v: number): number {
  return Math.max(0, Math.min(1, v));
}

export function SlipRow({ rank, slotMultiplier, player, slateDate }: Props) {
  const teamColor = teamPrimary(player.team);
  const ink = teamInk(player.team);
  const hasBoost = player.card_boost > 0;
  const hasScoreBand =
    typeof player.pred_real_score_p10 === "number" &&
    typeof player.pred_real_score_p90 === "number";

  // Decorative-only spread indicator, not a scale with labeled ticks:
  // position/width are this player's own p10-p90 as a fraction of
  // p90*1.15 (headroom so the band never touches the right edge).
  let bandLeftPct = 0;
  let bandWidthPct = 0;
  if (hasScoreBand) {
    const p10 = player.pred_real_score_p10 as number;
    const p90 = player.pred_real_score_p90 as number;
    const domainMax = p90 * 1.15 || 1;
    const left = clamp01(p10 / domainMax) * 100;
    const right = clamp01(p90 / domainMax) * 100;
    bandLeftPct = left;
    bandWidthPct = Math.max(4, right - left);
  }

  return (
    <Link
      to={`/player/${slateDate}/${player.player_id}`}
      className="slip-row"
      style={{
        ["--team-primary" as string]: teamColor,
        ["--team-ink" as string]: ink,
      }}
      aria-label={`Rank ${rank}. ${player.display_name}, ${player.team} versus ${player.opponent || "unknown"}, ${player.position}. Slot multiplier ${slotMultiplier.toFixed(2)}. Projected ${player.pred_real_score_p50.toFixed(1)}.`}
    >
      <span className="slip-row__rank" aria-hidden="true">
        {rank}
      </span>

      <span className="slip-row__identity">
        <Headshot name={player.display_name} size={40} />
        <span className="slip-row__identity-text">
          <span className="slip-row__name">{player.display_name}</span>
          <span className="slip-row__meta">
            <span className="slip-row__meta-text">
              {player.team} vs {player.opponent || "—"} &middot; {player.position}
            </span>
            <span className="slip-row__slot-mobile">
              &times;{slotMultiplier.toFixed(2)}
            </span>
            {hasBoost ? <BoostBadge cardBoost={player.card_boost} /> : null}
          </span>
        </span>
      </span>

      <span className="slip-row__slot" aria-hidden="true">
        &times;{slotMultiplier.toFixed(2)}
      </span>

      <span className="slip-row__proj-minutes">
        <span className="slip-row__proj" aria-hidden="true">
          <span className="slip-row__proj-num">
            {player.pred_real_score_p50.toFixed(1)}
          </span>
          {hasScoreBand ? (
            <span className="slip-row__proj-band-track">
              <span
                className="slip-row__proj-band"
                style={{ left: `${bandLeftPct}%`, width: `${bandWidthPct}%` }}
              />
            </span>
          ) : null}
        </span>

        <span className="slip-row__minutes">
          <IntervalBar
            compact
            p10={player.pred_minutes_p10}
            p50={player.pred_minutes_p50}
            p90={player.pred_minutes_p90}
            min={0}
            max={40}
            unit="m"
            ariaLabel={`Predicted minutes: P10 ${player.pred_minutes_p10.toFixed(0)}, median ${player.pred_minutes_p50.toFixed(0)}, P90 ${player.pred_minutes_p90.toFixed(0)}.`}
          />
        </span>
      </span>

      <span className="slip-row__live" aria-hidden="true">
        <span className="slip-row__live-placeholder">&mdash;</span>
      </span>
    </Link>
  );
}
