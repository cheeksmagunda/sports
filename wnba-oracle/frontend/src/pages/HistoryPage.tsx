import { useEffect, useState } from "react";
import { Shell } from "../components/Shell";
import { API_URL } from "../lib/api";

interface SlateOutcome {
  date: string;
  projectedScore: number;
  actualScore: number;
  diff: number;
  win: boolean;
}

export function HistoryPage() {
  const [outcomes, setOutcomes] = useState<SlateOutcome[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const r = await fetch(`${API_URL}/history`);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        setOutcomes((await r.json()) as SlateOutcome[]);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const winCount = outcomes.filter((o) => o.win).length;
  const lossCount = outcomes.length - winCount;
  const avgDiff = outcomes.length > 0 ? outcomes.reduce((sum, o) => sum + o.diff, 0) / outcomes.length : 0;

  return (
    <Shell slateDateDisplay="HISTORY">
      <div className="history-page">
        <div className="history-page__header">
          <h1>Track Record</h1>
        </div>

        {loading && <p className="history-page__message">Loading...</p>}
        {error && <p className="history-page__message history-page__message--error">{error}</p>}

        {!loading && !error && (
          <>
            <div className="history-page__stats">
              <div className="history-page__stat">
                <div className="history-page__stat-label">Slates</div>
                <div className="history-page__stat-value">{outcomes.length}</div>
              </div>
              <div className="history-page__stat">
                <div className="history-page__stat-label">Wins</div>
                <div className="history-page__stat-value history-page__stat-value--win">{winCount}</div>
              </div>
              <div className="history-page__stat">
                <div className="history-page__stat-label">Losses</div>
                <div className="history-page__stat-value history-page__stat-value--loss">{lossCount}</div>
              </div>
              <div className="history-page__stat">
                <div className="history-page__stat-label">Avg Diff</div>
                <div className="history-page__stat-value">{avgDiff.toFixed(1)}</div>
              </div>
            </div>

            {outcomes.length > 0 && (
              <div className="history-page__table-wrap">
                <table className="history-page__table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Projected</th>
                      <th>Actual</th>
                      <th>Diff</th>
                      <th>Result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {outcomes.map((o) => (
                      <tr key={o.date} className="history-page__row">
                        <td className="history-page__cell history-page__cell--date">
                          <a href={`/slate/${o.date}`}>{new Date(o.date).toLocaleDateString()}</a>
                        </td>
                        <td className="history-page__cell">{o.projectedScore.toFixed(1)}</td>
                        <td className="history-page__cell">{o.actualScore.toFixed(1)}</td>
                        <td className="history-page__cell">{o.diff > 0 ? "+" : ""}{o.diff.toFixed(1)}</td>
                        <td className={`history-page__cell history-page__cell--${o.win ? "win" : "loss"}`}>
                          {o.win ? "W" : "L"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </Shell>
  );
}
