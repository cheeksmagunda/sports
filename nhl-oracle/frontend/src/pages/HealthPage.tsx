import { useEffect, useState } from "react";
import { Shell } from "../components/Shell";
import { API_URL, fetchHealth, type HealthStatus } from "../lib/api";

type LoadState =
  | { kind: "loading" }
  | { kind: "ok"; data: HealthStatus }
  | { kind: "error"; message: string };

export function HealthPage() {
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await fetchHealth();
        if (!cancelled) setState({ kind: "ok", data });
      } catch (error) {
        if (!cancelled) {
          setState({
            kind: "error",
            message:
              error instanceof Error
                ? error.message
                : "Unable to reach the NHL API /health endpoint",
          });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <Shell eyebrow="Health">
      <section className="panel">
        <p className="panel__kicker">API probe</p>
        <h1 className="panel__title">/health</h1>
        <p className="panel__body">
          Client talks to <code>{API_URL}/health</code>. Until the hosted NHL
          API is online, expect a connection or HTTP failure here.
        </p>
        {state.kind === "loading" && (
          <p className="panel__status" role="status">
            Checking health&hellip;
          </p>
        )}
        {state.kind === "ok" && (
          <pre className="panel__code" role="status">
            {JSON.stringify(state.data, null, 2)}
          </pre>
        )}
        {state.kind === "error" && (
          <p className="panel__status panel__status--warn" role="status">
            API not reachable yet: {state.message}
          </p>
        )}
      </section>
    </Shell>
  );
}
