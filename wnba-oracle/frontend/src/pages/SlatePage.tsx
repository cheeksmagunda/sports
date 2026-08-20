import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Shell } from "../components/Shell";
import { Slip } from "../components/Slip";
import { SlateBand } from "../components/SlateBand";
import { fetchLineupForDate } from "../lib/api";
import { fetchScoreboard, fetchSummary, toEspnDate, type PlayerBoxLine } from "../lib/espn";
import { combineBoxLines } from "../lib/playerMatch";
import type { FrozenLineup } from "../lib/api";

export function SlatePage() {
  const { date } = useParams<{ date: string }>();
  const [lineup, setLineup] = useState<FrozenLineup | null>(null);
  const [boxLines, setBoxLines] = useState<PlayerBoxLine[]>([]);
  const [loading, setLoading] = useState(!!date);
  const [error, setError] = useState<string | null>(date ? null : "Invalid date");

  useEffect(() => {
    if (!date) return;

    const load = async () => {
      try {
        const lineupData = await fetchLineupForDate(date);
        if (!lineupData) {
          setError("Slate not found");
          setLoading(false);
          return;
        }
        setLineup(lineupData);

        try {
          const games = await fetchScoreboard(toEspnDate(date));
          const eventIds = games.map((g) => g.eventId);
          const allLines = await Promise.all(eventIds.map((id) => fetchSummary(id)));
          setBoxLines(allLines.flat());
        } catch {
          // ESPN data is enrichment only; proceed without live stats
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [date]);

  const combined = lineup && lineup.lineup.per_player ? combineBoxLines(lineup.lineup.per_player, boxLines) : null;

  return (
    <Shell slateDateDisplay={date?.toUpperCase()}>
      <div className="slate-page">
        {loading && <p className="slate-page__message">Loading...</p>}
        {error && <p className="slate-page__message slate-page__message--error">{error}</p>}

        {lineup && (
          <>
            {combined && (
              <SlateBand
                lineup={lineup}
                lifecycleState="final"
                combined={combined}
                gamesRemaining={0}
              />
            )}
            <Slip
              lineup={lineup}
              lifecycleState="final"
              boxLines={boxLines}
            />
          </>
        )}
      </div>
    </Shell>
  );
}
