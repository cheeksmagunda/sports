// A historical slate in the Tonight layout, always in final state. Built
// in Phase 5 by reusing the Slip/SlateBand components unchanged; this
// stub only proves the route resolves.

import { useParams } from "react-router-dom";
import { Shell } from "../components/Shell";

export function SlatePage() {
  const { date } = useParams();

  return (
    <Shell>
      <main className="stub-page" aria-label="Historical slate">
        <h1>Slate: {date}</h1>
        <p>The historical replay of this slate is coming in Phase 5.</p>
      </main>
    </Shell>
  );
}
