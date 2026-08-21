import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Shell } from "../components/Shell";
import { Headshot } from "../components/Headshot";
import { fetchLineupForDate, type PlayerProjection } from "../lib/api";
import { fetchScoreboard, fetchSummary, toEspnDate, type PlayerBoxLine } from "../lib/espn";
import { resolveBoxLine } from "../lib/playerMatch";
import { teamPrimary, teamInk } from "../lib/teams";

export function PlayerPage() {
  const { date, playerId } = useParams<{ date: string; playerId: string }>();
  const [player, setPlayer] = useState<PlayerProjection | null>(null);
  const [boxLine, setBoxLine] = useState<PlayerBoxLine | null>(null);
  const [loading, setLoading] = useState(!!date && !!playerId);
  const [error, setError] = useState<string | null>(!date || !playerId ? "Invalid parameters" : null);

  useEffect(() => {
    if (!date || !playerId) return;

    const load = async () => {
      try {
        const lineupData = await fetchLineupForDate(date);
        if (!lineupData) {
          setError("Slate not found");
          setLoading(false);
          return;
        }

        // Find the player in the lineup
        const foundPlayer = (lineupData.lineup.per_player ?? []).find(
          (p) => String(p.player_id) === playerId ||
            p.display_name.replace(/\s+/g, "-").toLowerCase() === playerId.toLowerCase(),
        );

        if (!foundPlayer) {
          setError("Player not found in this slate");
          setLoading(false);
          return;
        }
        setPlayer(foundPlayer);

        // Fetch box line if available
        try {
          const games = await fetchScoreboard(toEspnDate(date));
          const eventIds = games.map((g) => g.eventId);
          const allLines = await Promise.all(eventIds.map((id) => fetchSummary(id)));
          const boxLines = allLines.flat();
          const resolved = resolveBoxLine(foundPlayer.display_name, foundPlayer.team, boxLines);
          if (resolved) setBoxLine(resolved);
        } catch {
          // ESPN data is enrichment only
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [date, playerId]);

  if (loading) return <Shell slateDateDisplay={date?.toUpperCase()}><p className="player-page__message">Loading player details...</p></Shell>;
  if (error || !player) return <Shell slateDateDisplay={date?.toUpperCase()}><p className="player-page__message player-page__message--error">{error || "Player not found"}</p></Shell>;

  const primaryColor = teamPrimary(player.team);
  const inkColor = teamInk(player.team);

  return (
    <Shell slateDateDisplay={date?.toUpperCase()}>
      <div className="player-page" style={{ "--team-primary": primaryColor, "--team-ink": inkColor } as React.CSSProperties}>
        <div className="player-page__header">
          <Headshot name={player.display_name} size={80} espnAthleteId={boxLine?.espnAthleteId ?? null} />
          <div className="player-page__title">
            <h1>{player.display_name}</h1>
            <div className="player-page__meta">
              <span>{player.team}</span>
              <span>{player.position}</span>
              <span>vs {player.opponent}</span>
            </div>
          </div>
        </div>

        <div className="player-page__sections">
          <section className="player-page__section">
            <h2>Projection</h2>
            <div className="player-page__stats-grid">
              <div className="player-page__stat-item">
                <div className="player-page__stat-label">P50 Score</div>
                <div className="player-page__stat-value">{player.pred_real_score_p50.toFixed(1)}</div>
              </div>
              {player.pred_real_score_p10 !== undefined && (
                <div className="player-page__stat-item">
                  <div className="player-page__stat-label">P10 Score</div>
                  <div className="player-page__stat-value">{player.pred_real_score_p10.toFixed(1)}</div>
                </div>
              )}
              {player.pred_real_score_p90 !== undefined && (
                <div className="player-page__stat-item">
                  <div className="player-page__stat-label">P90 Score</div>
                  <div className="player-page__stat-value">{player.pred_real_score_p90.toFixed(1)}</div>
                </div>
              )}
              <div className="player-page__stat-item">
                <div className="player-page__stat-label">Minutes P50</div>
                <div className="player-page__stat-value">{player.pred_minutes_p50.toFixed(1)}</div>
              </div>
            </div>
          </section>

          {boxLine && (
            <section className="player-page__section">
              <h2>Actual Performance</h2>
              <div className="player-page__stats-grid">
                <div className="player-page__stat-item">
                  <div className="player-page__stat-label">Points</div>
                  <div className="player-page__stat-value">{boxLine.points ?? "--"}</div>
                </div>
                <div className="player-page__stat-item">
                  <div className="player-page__stat-label">Rebounds</div>
                  <div className="player-page__stat-value">{boxLine.rebounds ?? "--"}</div>
                </div>
                <div className="player-page__stat-item">
                  <div className="player-page__stat-label">Assists</div>
                  <div className="player-page__stat-value">{boxLine.assists ?? "--"}</div>
                </div>
                <div className="player-page__stat-item">
                  <div className="player-page__stat-label">Steals</div>
                  <div className="player-page__stat-value">{boxLine.steals ?? "--"}</div>
                </div>
                <div className="player-page__stat-item">
                  <div className="player-page__stat-label">Blocks</div>
                  <div className="player-page__stat-value">{boxLine.blocks ?? "--"}</div>
                </div>
                <div className="player-page__stat-item">
                  <div className="player-page__stat-label">Minutes</div>
                  <div className="player-page__stat-value">{boxLine.minutes ?? "--"}</div>
                </div>
              </div>
            </section>
          )}
        </div>
      </div>
    </Shell>
  );
}
