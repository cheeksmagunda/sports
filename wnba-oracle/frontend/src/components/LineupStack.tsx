// Five-card grid. Cards are emitted in the order they were optimized;
// rank is purely positional (1..5). CSS animations stagger the entry.

import type { FrozenLineup, PlayerProjection } from "../lib/api";
import { PlayerCard } from "./PlayerCard";

interface Props {
  lineup: FrozenLineup;
}

export function LineupStack({ lineup }: Props) {
  const projections = lineup.lineup.per_player ?? [];
  const ids = lineup.lineup.player_ids;
  const mults = lineup.lineup.slot_multipliers;

  // Fallback when API hasn't joined per-player projections (older slate
  // freezes pre-D32). Render placeholder cards so the layout doesn't
  // collapse, but with neutral data.
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
    <div
      role="list"
      aria-label="Five-player frozen lineup"
      className="grid"
    >
      {cards.map((p, i) => (
        <div role="listitem" key={p.player_id}>
          <PlayerCard
            rank={i + 1}
            slotMultiplier={mults[i] ?? 1}
            player={p}
          />
        </div>
      ))}
    </div>
  );
}
