// Five ordered rows, read top to bottom as an ordered list so screen
// readers announce rank first. Replaces the five-card grid.

import type { FrozenLineup, PlayerProjection } from "../lib/api";
import { SlipRow } from "./SlipRow";

interface Props {
  lineup: FrozenLineup;
}

export function Slip({ lineup }: Props) {
  const projections = lineup.lineup.per_player ?? [];
  const ids = lineup.lineup.player_ids;
  const mults = lineup.lineup.slot_multipliers;

  // Fallback when the API hasn't joined per-player projections (older
  // slate freezes pre-D32, still reachable via /lineup/{date}/history).
  // Synthesize placeholder rows so the layout doesn't collapse.
  const rows: PlayerProjection[] =
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
    <ol className="slip" aria-label="Five-player frozen lineup, ranked">
      {rows.map((p, i) => (
        <li key={p.player_id} className="slip__item">
          <SlipRow
            rank={i + 1}
            slotMultiplier={mults[i] ?? 1}
            player={p}
            slateDate={lineup.slate_date}
          />
        </li>
      ))}
    </ol>
  );
}
