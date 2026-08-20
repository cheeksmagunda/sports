// Every freeze for a slate, with a diff of what changed. Built in Phase
// 5; this stub only proves the route resolves.

import { useParams } from "react-router-dom";
import { Shell } from "../components/Shell";

export function FreezesPage() {
  const { date } = useParams();

  return (
    <Shell>
      <main className="stub-page" aria-label="Freeze log">
        <h1>Freeze log: {date}</h1>
        <p>The freeze-by-freeze diff for this slate is coming in Phase 5.</p>
      </main>
    </Shell>
  );
}
