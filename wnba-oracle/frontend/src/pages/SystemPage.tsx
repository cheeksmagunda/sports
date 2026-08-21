import { useEffect, useState } from "react";
import { Shell } from "../components/Shell";
import { fetchWatchdogToday, type WatchdogToday } from "../lib/api";

export function SystemPage() {
  const [status, setStatus] = useState<WatchdogToday | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        setStatus(await fetchWatchdogToday());
      } catch (e) {
        setError(e instanceof Error ? e.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  return (
    <Shell slateDateDisplay="SYSTEM">
      <div className="system-page">
        <div className="system-page__header">
          <span className="page-kicker">Operational monitor</span>
          <h1>System Status</h1>
          <p className="page-intro">The production watchdog checks the data and freeze pipeline before tonight&rsquo;s lineup is served.</p>
        </div>

        {loading && <p className="system-page__message">Checking the watchdog...</p>}
        {error && <p className="system-page__message system-page__message--error">Unable to reach the watchdog. {error}</p>}

        {status && (
          <div className="system-page__content">
            <div className="system-page__summary">
              <div>
                <div className="system-page__label">Watchdog status</div>
                <span className={`system-page__status system-page__status--${status.status}`}>
                  {status.status === "ok" ? "All clear" : status.status}
                </span>
              </div>
              <div>
                <div className="system-page__label">Last checked</div>
                <time>{new Date(status.checked_at_utc).toLocaleString()}</time>
              </div>
              <div>
                <div className="system-page__label">Alerts</div>
                <strong>{status.events.length}</strong>
              </div>
            </div>
            {status.events.length > 0 ? (
              <div className="system-page__events">
                {status.events.map((event, index) => (
                  <div key={`${event.created_at ?? "event"}-${index}`} className={`system-page__event system-page__event--${event.severity}`}>
                    <span className="system-page__event-severity">{event.severity}</span>
                    <span className="system-page__event-trigger">{event.trigger.replaceAll("_", " ")}</span>
                    <time>{event.created_at ? new Date(event.created_at).toLocaleString() : "—"}</time>
                  </div>
                ))}
              </div>
            ) : <p className="system-page__message">No active watchdog events.</p>}
          </div>
        )}
      </div>
    </Shell>
  );
}
