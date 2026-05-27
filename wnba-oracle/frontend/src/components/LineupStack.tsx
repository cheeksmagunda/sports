import type { FrozenLineup, PlayerProjection } from "../lib/api";
import { PlayerCard } from "./PlayerCard";

type Props = { lineup: FrozenLineup };

export function LineupStack({ lineup }: Props) {
  const projections = lineup.lineup.per_player ?? [];
  const ids = lineup.lineup.player_ids;
  const mults = lineup.lineup.slot_multipliers;

  // Fallback when API hasn't joined per-player projections yet.
  const cards: PlayerProjection[] =
    projections.length === ids.length
      ? projections
      : ids.map((pid) => ({
          player_id: pid,
          display_name: `Player ${pid}`,
          team: "—",
          opponent: "—",
          position: "F",
          card_boost: 0,
          pred_real_score_p50: 0,
          pred_minutes_p10: 0,
          pred_minutes_p50: 0,
          pred_minutes_p90: 0,
        }));

  return (
    <div>
      <p className="slate-meta" style={{ marginTop: 8 }}>
        EV {lineup.expected_payout.toFixed(2)} ·{" "}
        lineup P10 / P50 / P90:{" "}
        {lineup.lineup.lineup_score_p10.toFixed(1)} /{" "}
        {lineup.lineup.lineup_score_p50.toFixed(1)} /{" "}
        {lineup.lineup.lineup_score_p90.toFixed(1)} ·{" "}
        regime {lineup.payout_regime}
      </p>
      <div className="lineup-stack">
        {cards.map((p, idx) => (
          <PlayerCard
            key={p.player_id}
            slotMultiplier={mults[idx] ?? 0}
            slotRank={idx + 1}
            player={p}
          />
        ))}
      </div>
    </div>
  );
}
