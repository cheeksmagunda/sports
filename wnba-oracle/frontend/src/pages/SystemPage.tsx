// Model SHA, payout curve, serving knobs, watchdog events, API health.
// Built in Phase 5; this stub only proves the route resolves and the
// watchdog dot has somewhere to land.

import { Shell } from "../components/Shell";

export function SystemPage() {
  return (
    <Shell>
      <main className="stub-page" aria-label="System status">
        <h1>System</h1>
        <p>Model provenance and watchdog detail are coming in Phase 5.</p>
      </main>
    </Shell>
  );
}
