import { useCallback, useEffect, useState } from "react";
import { Shell } from "../components/Shell";
import { API_URL, fetchHealth, type HealthStatus } from "../lib/api";

export function SystemPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null);

  const load = useCallback(async () => {
    setHealth(await fetchHealth());
  }, []);

  useEffect(() => {
    const t = setTimeout(() => {
      void load();
    }, 0);
    return () => clearTimeout(t);
  }, [load]);

  return (
    <Shell apiStatus={health?.status ?? "pending"}>
      <div className="stub-page">
        <h1>System</h1>
        <p>
          NHL Oracle frontend scaffold. API origin:{" "}
          <code className="home__mono">{API_URL}</code>
        </p>
        <p>
          Expected routes:{" "}
          <code className="home__mono">/health</code>,{" "}
          <code className="home__mono">/slate/{"{date}"}</code>,{" "}
          <code className="home__mono">/lineup/{"{date}"}</code>.
        </p>
        {health ? (
          <p>
            Health: <strong>{health.status}</strong>
            {health.detail ? ` — ${health.detail}` : null}
          </p>
        ) : (
          <p>Checking health&hellip;</p>
        )}
        <p>
          <button type="button" className="error-state__retry" onClick={() => void load()}>
            Refresh health
          </button>
        </p>
      </div>
    </Shell>
  );
}
