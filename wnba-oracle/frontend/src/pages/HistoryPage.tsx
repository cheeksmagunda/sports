import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { Shell } from "../components/Shell";
import { fetchRecentSlates, type SlateSummary } from "../lib/api";

export function HistoryPage() {
  const [slates, setSlates] = useState<SlateSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        setSlates(await fetchRecentSlates());
      } catch (e) {
        setError(e instanceof Error ? e.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const enterCount = slates.filter((s) => s.entry_recommendation === "enter").length;
  const avgPayout = slates.length > 0
    ? slates.reduce((sum, slate) => sum + slate.expected_payout, 0) / slates.length
    : 0;
  const latestFreeze = slates[0]?.frozen_at;

  return (
    <Shell slateDateDisplay="HISTORY">
      <div className="history-page">
        <div className="history-page__header">
          <span className="page-kicker">Frozen lineup archive</span>
          <h1>Slate History</h1>
          <p className="page-intro">Review the decisions the oracle actually froze, with their model and payout context.</p>
        </div>

        {loading && <p className="history-page__message">Loading recent slates...</p>}
        {error && <p className="history-page__message history-page__message--error">Unable to load slate history. {error}</p>}

        {!loading && !error && (
          <>
            <div className="history-page__stats">
              <div className="history-page__stat">
                <div className="history-page__stat-label">Slates</div>
                <div className="history-page__stat-value">{slates.length}</div>
              </div>
              <div className="history-page__stat">
                <div className="history-page__stat-label">Enter Calls</div>
                <div className="history-page__stat-value history-page__stat-value--win">{enterCount}</div>
              </div>
              <div className="history-page__stat">
                <div className="history-page__stat-label">Average Payout</div>
                <div className="history-page__stat-value">{avgPayout.toFixed(2)}</div>
              </div>
              <div className="history-page__stat">
                <div className="history-page__stat-label">Latest Freeze</div>
                <div className="history-page__stat-value history-page__stat-value--date">
                  {latestFreeze ? new Date(latestFreeze).toLocaleDateString() : "—"}
                </div>
              </div>
            </div>

            {slates.length > 0 ? (
              <div className="history-page__table-wrap">
                <table className="history-page__table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Decision</th>
                      <th>Expected Payout</th>
                      <th>Freeze</th>
                      <th>Frozen At</th>
                    </tr>
                  </thead>
                  <tbody>
                    {slates.map((slate) => (
                      <tr key={`${slate.slate_date}-${slate.model_sha}`} className="history-page__row">
                        <td className="history-page__cell history-page__cell--date">
                          <Link to={`/slate/${slate.slate_date}`}>
                            {new Date(`${slate.slate_date}T12:00:00`).toLocaleDateString()}
                          </Link>
                        </td>
                        <td className={`history-page__cell history-page__cell--${slate.entry_recommendation}`}>
                          {slate.entry_recommendation.replaceAll("_", " ")}
                        </td>
                        <td className="history-page__cell history-page__cell--numeric">
                          {slate.expected_payout.toFixed(2)}
                        </td>
                        <td className="history-page__cell history-page__cell--numeric">
                          #{slate.freeze_seq}
                        </td>
                        <td className="history-page__cell history-page__cell--muted">
                          {slate.frozen_at ? new Date(slate.frozen_at).toLocaleString() : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <p className="history-page__message">No frozen slates are available yet.</p>}
          </>
        )}
      </div>
    </Shell>
  );
}
