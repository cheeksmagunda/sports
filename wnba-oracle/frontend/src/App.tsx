import { useEffect, useState } from "react";
import { LineupStack } from "./components/LineupStack";
import type { FrozenLineup } from "./lib/api";
import { fetchLatestLineup } from "./lib/api";

export function App() {
  const [lineup, setLineup] = useState<FrozenLineup | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetchLatestLineup()
      .then((data) => {
        if (!cancelled) {
          setLineup(data);
          setLoading(false);
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setErr(e instanceof Error ? e.message : String(e));
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <div className="app-title">
            <span>WNBA</span> <span className="app-title-accent">Oracle</span>
          </div>
          <div className="slate-meta">
            {lineup ? `slate ${lineup.slate_date}` : loading ? "loading…" : "—"}
          </div>
        </div>
        {lineup && (
          <span className={`entry-flag entry-flag--${lineup.entry_recommendation}`}>
            {lineup.entry_recommendation.replaceAll("_", " ")}
          </span>
        )}
      </header>

      {err ? (
        <div className="error-state">
          <strong>API unreachable.</strong>{" "}
          {err}. Confirm <code>VITE_API_URL</code> and that{" "}
          <code>/lineup</code> has a frozen entry.
        </div>
      ) : loading ? (
        <div className="placeholder">contacting the oracle…</div>
      ) : lineup ? (
        <LineupStack lineup={lineup} />
      ) : (
        <div className="placeholder">no frozen lineup for today yet</div>
      )}
    </main>
  );
}
