import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Shell } from "../components/Shell";
import { API_URL } from "../lib/api";

interface FreezeVersion {
  freeze_seq: number;
  frozen_at: string;
  frozen_via: string;
  per_player: Array<{
    display_name: string;
    team: string;
    opponent: string;
    position: string;
  }>;
}

interface FreezeDiff {
  version: number;
  changedPlayers: Array<{
    name: string;
    team: string;
    status: "added" | "removed" | "reranked";
    detail?: string;
  }>;
}

export function FreezesPage() {
  const { date } = useParams<{ date: string }>();
  const [freezes, setFreezes] = useState<FreezeVersion[]>([]);
  const [diffs, setDiffs] = useState<Map<number, FreezeDiff>>(new Map());
  const [loading, setLoading] = useState(!!date);
  const [error, setError] = useState<string | null>(date ? null : "Invalid date");

  useEffect(() => {
    if (!date) return;

    const load = async () => {
      try {
        const r = await fetch(`${API_URL}/freezes/${date}`);
        if (r.status === 404) {
          setError("No freezes found for this date");
          setLoading(false);
          return;
        }
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data = (await r.json()) as FreezeVersion[];
        setFreezes(data);

        // Compute diffs between consecutive freezes
        const diffMap = new Map<number, FreezeDiff>();
        for (let i = 1; i < data.length; i++) {
          const prev = new Set(data[i - 1].per_player.map((p) => `${p.display_name}|${p.team}`));
          const curr = new Set(data[i].per_player.map((p) => `${p.display_name}|${p.team}`));
          const changedPlayers = [];

          for (const key of curr) {
            if (!prev.has(key)) {
              const player = data[i].per_player.find((p) => `${p.display_name}|${p.team}` === key);
              if (player) changedPlayers.push({ name: player.display_name, team: player.team, status: "added" as const });
            }
          }
          for (const key of prev) {
            if (!curr.has(key)) {
              const player = data[i - 1].per_player.find((p) => `${p.display_name}|${p.team}` === key);
              if (player) changedPlayers.push({ name: player.display_name, team: player.team, status: "removed" as const });
            }
          }

          diffMap.set(data[i].freeze_seq, { version: data[i].freeze_seq, changedPlayers });
        }
        setDiffs(diffMap);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [date]);

  return (
    <Shell slateDateDisplay={date?.toUpperCase()}>
      <div className="freezes-page">
        <div className="freezes-page__header">
          <h1>Freeze History</h1>
        </div>

        {loading && <p className="freezes-page__message">Loading...</p>}
        {error && <p className="freezes-page__message freezes-page__message--error">{error}</p>}

        {freezes.length > 0 && (
          <div className="freezes-page__list">
            {freezes.map((freeze) => {
              const diff = diffs.get(freeze.freeze_seq);
              return (
                <div key={freeze.freeze_seq} className="freezes-page__item">
                  <div className="freezes-page__item-header">
                    <h3>Freeze #{freeze.freeze_seq}</h3>
                    <time>{new Date(freeze.frozen_at).toLocaleTimeString()}</time>
                    <span className="freezes-page__via">{freeze.frozen_via}</span>
                  </div>

                  {diff && diff.changedPlayers.length > 0 && (
                    <div className="freezes-page__changes">
                      {diff.changedPlayers.map((change, idx) => (
                        <div key={idx} className={`freezes-page__change freezes-page__change--${change.status}`}>
                          <span className="freezes-page__change-status">{change.status}</span>
                          <span className="freezes-page__change-name">{change.name}</span>
                          <span className="freezes-page__change-team">{change.team}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  {(!diff || diff.changedPlayers.length === 0) && (
                    <p className="freezes-page__no-changes">No changes</p>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </Shell>
  );
}
