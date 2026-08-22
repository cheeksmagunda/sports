// Five ordered rows, read top to bottom as an ordered list so screen
// readers announce rank first. Replaces the five-card grid.

import type { FrozenLineup } from "../lib/api";
import type { SlateLifecycleState } from "../hooks/useSlateLifecycle";
import type { PlayerBoxLine } from "../lib/espn";
import { resolveOrderedLineup } from "../lib/lineup";
import { resolveBoxLine } from "../lib/playerMatch";
import { ErrorState } from "./ErrorState";
import { SlipRow } from "./SlipRow";

interface Props {
  lineup: FrozenLineup;
  boxLines?: PlayerBoxLine[];
  lifecycleState?: SlateLifecycleState;
}

export function Slip({ lineup, boxLines = [], lifecycleState }: Props) {
  const orderedLineup = resolveOrderedLineup(lineup.lineup);

  if (!orderedLineup.ok) {
    return (
      <ErrorState
        title="Lineup unavailable"
        copy="This frozen lineup cannot be displayed safely."
        detail={orderedLineup.error}
      />
    );
  }

  return (
    <ol className="slip" aria-label="Five-player frozen lineup, ranked">
      {orderedLineup.rows.map(({ player, slotMultiplier }, index) => (
        <li key={player.player_id} className="slip__item">
          <SlipRow
            rank={index + 1}
            slotMultiplier={slotMultiplier}
            player={player}
            slateDate={lineup.slate_date}
            boxLine={resolveBoxLine(
              player.display_name,
              player.team,
              boxLines,
            )}
            lifecycleState={lifecycleState}
          />
        </li>
      ))}
    </ol>
  );
}
