import { useEffect, useState } from "react";
import { Shell } from "../components/Shell";
import { API_URL } from "../lib/api";

interface SystemStatus {
  buildSha?: string;
  buildTime?: string;
  modelSha?: string;
  modelDate?: string;
  databaseHealthy?: boolean;
  redisHealthy?: boolean;
  lastJobRun?: string;
  nextJobRun?: string;
}

export function SystemPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const r = await fetch(`${API_URL}/system`);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        setStatus((await r.json()) as SystemStatus);
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
          <h1>System Status</h1>
        </div>

        {loading && <p className="system-page__message">Loading...</p>}
        {error && <p className="system-page__message system-page__message--error">{error}</p>}

        {status && (
          <div className="system-page__grid">
            {status.buildSha && (
              <div className="system-page__item">
                <div className="system-page__label">Frontend Build</div>
                <code className="system-page__code">{status.buildSha.slice(0, 8)}</code>
              </div>
            )}
            {status.buildTime && (
              <div className="system-page__item">
                <div className="system-page__label">Built At</div>
                <time>{new Date(status.buildTime).toLocaleString()}</time>
              </div>
            )}
            {status.modelSha && (
              <div className="system-page__item">
                <div className="system-page__label">Model</div>
                <code className="system-page__code">{status.modelSha.slice(0, 12)}</code>
              </div>
            )}
            {status.modelDate && (
              <div className="system-page__item">
                <div className="system-page__label">Model Trained</div>
                <time>{new Date(status.modelDate).toLocaleString()}</time>
              </div>
            )}
            {typeof status.databaseHealthy === "boolean" && (
              <div className="system-page__item">
                <div className="system-page__label">Database</div>
                <span
                  className={`system-page__status system-page__status--${
                    status.databaseHealthy ? "ok" : "error"
                  }`}
                >
                  {status.databaseHealthy ? "OK" : "Error"}
                </span>
              </div>
            )}
            {typeof status.redisHealthy === "boolean" && (
              <div className="system-page__item">
                <div className="system-page__label">Redis Cache</div>
                <span
                  className={`system-page__status system-page__status--${
                    status.redisHealthy ? "ok" : "error"
                  }`}
                >
                  {status.redisHealthy ? "OK" : "Error"}
                </span>
              </div>
            )}
            {status.lastJobRun && (
              <div className="system-page__item">
                <div className="system-page__label">Last Job Run</div>
                <time>{new Date(status.lastJobRun).toLocaleString()}</time>
              </div>
            )}
            {status.nextJobRun && (
              <div className="system-page__item">
                <div className="system-page__label">Next Job Run</div>
                <time>{new Date(status.nextJobRun).toLocaleString()}</time>
              </div>
            )}
          </div>
        )}
      </div>
    </Shell>
  );
}
