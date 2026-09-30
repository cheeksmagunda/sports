import { useCallback, useEffect, useState } from "react";
import { Navigate, useParams } from "react-router-dom";
import {
  centralDate,
  fetchHealth,
  fetchLineup,
  picksOf,
  type Health,
  type LineupPayload,
} from "../lib/api";
import { isSportId, SPORTS, type SportId } from "../lib/sports";

type Load<T> =
  | { kind: "loading" }
  | { kind: "ok"; data: T | null }
  | { kind: "error"; message: string };

const REFRESH_MS = 30_000;

function useLoad<T>(load: () => Promise<T | null>): [Load<T>, () => void] {
  const [state, setState] = useState<Load<T>>({ kind: "loading" });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let cancelled = false;
    load().then(
      (data) => !cancelled && setState({ kind: "ok", data }),
      (error: unknown) =>
        !cancelled &&
        setState({ kind: "error", message: error instanceof Error ? error.message : "Request failed" }),
    );
    return () => {
      cancelled = true;
    };
  }, [load, tick]);
  useEffect(() => {
    const id = globalThis.setInterval(() => {
      if (!document.hidden) setTick((n) => n + 1);
    }, REFRESH_MS);
    return () => globalThis.clearInterval(id);
  }, []);
  return [state, () => setTick((n) => n + 1)];
}

export function SportPage() {
  const { sport } = useParams<{ sport: string }>();
  if (!isSportId(sport)) return <Navigate to="/nfl" replace />;
  // key resets all state when switching tabs
  return <SportView key={sport} sport={sport} />;
}

function SportView({ sport }: { sport: SportId }) {
  const label = SPORTS.find((s) => s.id === sport)?.label ?? sport;
  const [day, setDay] = useState(centralDate);
  const loadLineup = useCallback(() => fetchLineup(sport, day), [sport, day]);
  const loadHealth = useCallback(() => fetchHealth(sport), [sport]);
  const [lineup, refresh] = useLoad<LineupPayload>(loadLineup);
  const [health] = useLoad<Health>(loadHealth);

  return (
    <div className="stack">
      <section className="panel">
        <div className="row">
          <h1 className="panel__title">{label}</h1>
          <label className="day">
            <span>Slate day</span>
            <input type="date" value={day} onChange={(e) => e.target.value && setDay(e.target.value)} />
          </label>
          <button type="button" className="button" onClick={refresh}>
            Refresh
          </button>
        </div>
        <HealthLine state={health} />
      </section>
      <LineupPanel state={lineup} />
    </div>
  );
}

function HealthLine({ state }: { state: Load<Health> }) {
  if (state.kind === "loading") return <p className="muted" role="status">Checking service</p>;
  if (state.kind === "error")
    return <p className="warn" role="status">Service not reachable: {state.message}</p>;
  if (!state.data) return <p className="warn" role="status">Service has no /health route yet</p>;
  return <p className="ok" role="status">Service {state.data.status}</p>;
}

function LineupPanel({ state }: { state: Load<LineupPayload> }) {
  if (state.kind === "loading") return <section className="panel"><p className="muted">Loading picks</p></section>;
  if (state.kind === "error")
    return (
      <section className="panel">
        <p className="warn">Cannot load picks: {state.message}</p>
      </section>
    );
  const payload = state.data;
  const picks = picksOf(payload);
  if (picks.length === 0) {
    return (
      <section className="panel">
        <p className="panel__kicker">No picks yet</p>
        <p className="muted">
          {payload?.status ? `Status: ${payload.status}. ` : ""}
          No frozen lineup is available for this day.
        </p>
      </section>
    );
  }
  return (
    <section className="panel">
      <p className="panel__kicker">
        Five picks{payload?.boost_regime ? ` · boost regime ${payload.boost_regime}` : ""}
      </p>
      <ol className="picks">
        {picks.map((pick, index) => (
          <li key={`${pick.name}-${index}`} className="pick">
            <span className="pick__rank" aria-hidden="true">{pick.slot ?? index + 1}</span>
            <span className="pick__who">
              <strong>{pick.name}</strong>
              <span className="muted">
                {[pick.team, pick.opponent ? `vs ${pick.opponent}` : null, pick.position]
                  .filter(Boolean)
                  .join(" · ")}
              </span>
            </span>
            {typeof pick.slot_multiplier === "number" && (
              <span className="muted">×{pick.slot_multiplier.toFixed(2)}</span>
            )}
            {typeof pick.projected_value === "number" && (
              <span className="pick__value">{pick.projected_value.toFixed(1)}</span>
            )}
          </li>
        ))}
      </ol>
      <p className="muted">Observation only. You place any entry yourself.</p>
    </section>
  );
}
