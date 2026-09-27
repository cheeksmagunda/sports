import { useCallback, useEffect, useState } from "react";
import { ErrorState } from "../components/ErrorState";
import { Shell } from "../components/Shell";
import {
  fetchHealth,
  fetchLatestLineup,
  localSlateDate,
  type FrozenLineup,
  type HealthStatus,
} from "../lib/api";

function fmtSlateDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  const date = new Date(y, m - 1, d, 12, 0, 0);
  return date
    .toLocaleDateString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
      year: "numeric",
    })
    .toUpperCase()
    .replaceAll(",", " ·");
}

type LoadState =
  | { kind: "loading" }
  | { kind: "ready"; health: HealthStatus; lineup: FrozenLineup | null }
  | { kind: "error"; message: string };

export function HomePage() {
  const slate = localSlateDate();
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const health = await fetchHealth();
      let lineup: FrozenLineup | null = null;
      try {
        lineup = await fetchLatestLineup();
      } catch {
        // Lineup route may not exist yet; health alone is enough for scaffold.
        lineup = null;
      }
      setState({ kind: "ready", health, lineup });
    } catch (error) {
      const message = error instanceof Error ? error.message : "load failed";
      setState({ kind: "error", message });
    }
  }, []);

  useEffect(() => {
    // Defer so the effect does not write loading state synchronously.
    const t = setTimeout(() => {
      void load();
    }, 0);
    return () => clearTimeout(t);
  }, [load]);

  const apiStatus =
    state.kind === "ready" ? state.health.status : state.kind;

  return (
    <Shell slateDateDisplay={fmtSlateDate(slate)} apiStatus={apiStatus}>
      <div className="home">
        <section className="home__hero" aria-labelledby="home-title">
          <p className="home__eyebrow">Sports Oracle · NHL</p>
          <h1 id="home-title" className="home__title">
            Tonight&rsquo;s five
          </h1>
          <p className="home__lede">
            Read-only shell for the five-card ordered NHL contest. Hosted API
            and freeze pipeline are not live yet; this UI is ready for
            nhl-frontend on nhl-staging.
          </p>
        </section>

        {state.kind === "loading" ? (
          <p className="home__status" role="status">
            Checking API&hellip;
          </p>
        ) : null}

        {state.kind === "error" ? (
          <ErrorState
            title="Could not reach the NHL API"
            copy="The frontend expected a public health endpoint. Retry when the API origin is reachable."
            detail={state.message}
            onRetry={() => void load()}
          />
        ) : null}

        {state.kind === "ready" ? (
          <div className="home__panel">
            <div className="home__status-row">
              <span
                className="home__pill"
                data-status={state.health.status}
              >
                {state.health.status}
              </span>
              <span className="home__mono">GET /health</span>
            </div>
            {state.health.detail ? (
              <p className="home__detail">{state.health.detail}</p>
            ) : null}
            {state.lineup ? (
              <p className="home__detail">
                Freeze seq {state.lineup.freeze_seq} · model{" "}
                {state.lineup.model_sha.slice(0, 12)}
              </p>
            ) : (
              <p className="home__detail">
                No lineup for {slate}.{" "}
                <span className="home__mono">
                  GET /lineup/{"{date}"}
                </span>{" "}
                returns 404 until the hosted API exists.
              </p>
            )}
            <ul className="home__slots" aria-label="Placeholder slot multipliers">
              {[2.0, 1.8, 1.6, 1.4, 1.2].map((m, i) => (
                <li key={m} className="home__slot">
                  <span className="home__slot-idx">{i + 1}</span>
                  <span className="home__slot-label">Slot ×{m.toFixed(1)}</span>
                  <span className="home__slot-empty">awaiting freeze</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </Shell>
  );
}
