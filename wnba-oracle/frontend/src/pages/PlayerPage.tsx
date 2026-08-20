// One pick, full depth: quantiles, archetype, streak, leverage, ESPN
// recent form, live/final box line. Built in Phase 5; this stub only
// proves the route resolves.

import { useParams } from "react-router-dom";
import { Shell } from "../components/Shell";

export function PlayerPage() {
  const { date, playerId } = useParams();

  return (
    <Shell>
      <main className="stub-page" aria-label="Player detail">
        <h1>Player detail</h1>
        <p>
          Full depth for player {playerId} on {date} is coming in Phase 5.
        </p>
      </main>
    </Shell>
  );
}
