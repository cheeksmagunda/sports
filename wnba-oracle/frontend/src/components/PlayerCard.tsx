import type { PlayerProjection } from "../lib/api";

type Props = {
  slotRank: number;
  slotMultiplier: number;
  player: PlayerProjection;
};

export function PlayerCard({ slotRank, slotMultiplier, player }: Props) {
  return (
    <article className="player-card" aria-label={`slot ${slotRank}`}>
      <div className="slot-badge" title={`slot multiplier ${slotMultiplier}x`}>
        {slotRank}
      </div>
      <div className="player-body">
        <div className="player-name">{player.display_name}</div>
        <div className="player-meta">
          <span className="position-badge">{player.position || "?"}</span>
          <span>
            {player.team} <span className="ms">vs</span> {player.opponent || "—"}
          </span>
          <span className="boost-badge">
            +{player.card_boost.toFixed(1)}x boost
          </span>
        </div>
        <div className="minutes-row">
          <span className="ms">min P10/P50/P90</span>{" "}
          {player.pred_minutes_p10.toFixed(0)} /{" "}
          {player.pred_minutes_p50.toFixed(0)} /{" "}
          {player.pred_minutes_p90.toFixed(0)}
        </div>
      </div>
      <div className="player-right">
        <div className="score-row">
          {player.pred_real_score_p50.toFixed(2)}
        </div>
        <div className="score-row-secondary">
          slot {slotMultiplier.toFixed(1)}x
        </div>
      </div>
    </article>
  );
}
