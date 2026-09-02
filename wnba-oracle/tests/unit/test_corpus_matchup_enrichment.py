"""D77: _enrich_corpus_matchup adds team_pace/opp_pace/opp_dvp to the corpus."""

from __future__ import annotations

from unittest.mock import patch

import polars as pl

from wnba_oracle.features.corpus import _enrich_corpus_matchup


def _make_corpus(n_teams: int = 2) -> pl.DataFrame:
    """Minimal corpus with team/opponent columns."""
    rows = []
    teams = ["LVA", "SEA", "NYL", "ATL"][:n_teams]
    opps = teams[1:] + teams[:1]
    for t, o in zip(teams, opps):
        for i in range(3):
            rows.append({"team": t, "opponent": o, "player_id": i + 1})
    return pl.DataFrame(rows)


def _make_game_logs(team: str = "LVA", opp: str = "SEA") -> pl.DataFrame:
    """Minimal game_logs with all stat cols for DvP computation."""
    return pl.DataFrame(
        [
            {
                "team": team,
                "opponent": opp,
                "min": 25.0,
                "pts": 20.0,
                "reb": 6.0,
                "oreb": 1.0,
                "dreb": 5.0,
                "ast": 3.0,
                "stl": 1.0,
                "blk": 0.5,
                "tov": 1.0,
                "fgm": 7.0,
                "fga": 14.0,
                "fg3m": 1.0,
                "ftm": 5.0,
                "fta": 6.0,
            },
            {
                "team": team,
                "opponent": opp,
                "min": 30.0,
                "pts": 25.0,
                "reb": 8.0,
                "oreb": 2.0,
                "dreb": 6.0,
                "ast": 5.0,
                "stl": 2.0,
                "blk": 1.0,
                "tov": 2.0,
                "fgm": 9.0,
                "fga": 18.0,
                "fg3m": 2.0,
                "ftm": 5.0,
                "fta": 6.0,
            },
        ]
    )


_FAKE_TEAM_STATS = {
    "LVA": {"pace": 90.0, "off_rtg": 115.0, "def_rtg": 108.0},
    "SEA": {"pace": 88.0, "off_rtg": 112.0, "def_rtg": 110.0},
}


def test_team_pace_injected_from_nba_api() -> None:
    corpus = _make_corpus()
    game_logs = _make_game_logs()
    with patch(
        "wnba_oracle.ingest.minutes_features.fetch_wnba_team_stats",
        return_value=_FAKE_TEAM_STATS,
    ):
        result = _enrich_corpus_matchup(corpus, game_logs)

    lva_rows = result.filter(pl.col("team") == "LVA")
    assert all(v == 90.0 for v in lva_rows["team_pace"].to_list())
    sea_rows = result.filter(pl.col("team") == "SEA")
    assert all(v == 88.0 for v in sea_rows["team_pace"].to_list())


def test_game_pace_implied_is_mean_of_team_and_opp() -> None:
    corpus = _make_corpus()
    game_logs = _make_game_logs()
    with patch(
        "wnba_oracle.ingest.minutes_features.fetch_wnba_team_stats",
        return_value=_FAKE_TEAM_STATS,
    ):
        result = _enrich_corpus_matchup(corpus, game_logs)

    lva_row = result.filter(pl.col("team") == "LVA").row(0, named=True)
    expected = (90.0 + 88.0) / 2.0
    assert abs(lva_row["game_pace_implied"] - expected) < 1e-9


def test_opp_dvp_populated_from_game_logs() -> None:
    corpus = _make_corpus()
    game_logs = _make_game_logs(team="LVA", opp="SEA")
    with patch(
        "wnba_oracle.ingest.minutes_features.fetch_wnba_team_stats",
        return_value={},
    ):
        result = _enrich_corpus_matchup(corpus, game_logs)

    # Rows where opponent is SEA should have non-zero DvP (SEA allowed points to LVA).
    sea_opp_rows = result.filter(pl.col("opponent") == "SEA")
    dvp_vals = sea_opp_rows["opp_dvp_forward"].to_list()
    assert all(v > 0 for v in dvp_vals), f"expected non-zero DvP, got {dvp_vals}"


def test_three_dvp_columns_always_present() -> None:
    corpus = _make_corpus()
    with patch(
        "wnba_oracle.ingest.minutes_features.fetch_wnba_team_stats",
        return_value={},
    ):
        result = _enrich_corpus_matchup(corpus, pl.DataFrame())

    for col in ("opp_dvp_guard", "opp_dvp_forward", "opp_dvp_center"):
        assert col in result.columns


def test_degrades_gracefully_on_nba_api_failure() -> None:
    corpus = _make_corpus()
    with patch(
        "wnba_oracle.ingest.minutes_features.fetch_wnba_team_stats",
        side_effect=RuntimeError("network down"),
    ):
        result = _enrich_corpus_matchup(corpus, pl.DataFrame())

    # team_pace should be 0 (fallback), no crash
    assert "team_pace" in result.columns
    assert all(v == 0.0 for v in result["team_pace"].to_list())


# -- point-in-time DvP -------------------------------------------------------


def _dated_game_logs() -> pl.DataFrame:
    """Two dates. On 05-01 LVA scores big against SEA; on 05-03 LVA scores
    little against SEA. A causal 05-03 row may only see the 05-01 game."""
    base = {
        "reb": 0.0,
        "oreb": 0.0,
        "dreb": 0.0,
        "ast": 0.0,
        "stl": 0.0,
        "blk": 0.0,
        "tov": 0.0,
        "fgm": 0.0,
        "fga": 0.0,
        "fg3m": 0.0,
        "ftm": 0.0,
        "fta": 0.0,
        "min": 30.0,
    }
    return pl.DataFrame(
        [
            {"game_date": "2026-05-01", "team": "LVA", "opponent": "SEA", "pts": 40.0, **base},
            {"game_date": "2026-05-03", "team": "LVA", "opponent": "SEA", "pts": 10.0, **base},
        ]
    )


def _dated_corpus() -> pl.DataFrame:
    return pl.DataFrame(
        [
            {"game_date": "2026-05-01", "team": "LVA", "opponent": "SEA", "player_id": 1},
            {"game_date": "2026-05-03", "team": "LVA", "opponent": "SEA", "player_id": 1},
            {"game_date": "2026-05-03", "team": "SEA", "opponent": "LVA", "player_id": 2},
            {"game_date": "2026-05-03", "team": "LVA", "opponent": "sea", "player_id": 3},
        ]
    )


def test_causal_dvp_uses_only_strictly_prior_games() -> None:
    from wnba_oracle.features.game_features import compute_opp_dvp_map

    logs = _dated_game_logs()
    with patch("wnba_oracle.ingest.minutes_features.fetch_wnba_team_stats", return_value={}):
        result = _enrich_corpus_matchup(_dated_corpus(), logs, causal_dvp=True)

    by = {(r["game_date"], r["player_id"]): r for r in result.to_dicts()}
    # First appearance of SEA as an opponent: no prior games -> 0.0, never the
    # row's own game.
    assert by[("2026-05-01", 1)]["opp_dvp_forward"] == 0.0
    # 05-03 row sees only the 05-01 game (pts=40), not its own 10-pt game.
    expected = compute_opp_dvp_map(logs.filter(pl.col("game_date") < "2026-05-03"))["SEA"]
    assert abs(by[("2026-05-03", 1)]["opp_dvp_forward"] - expected) < 1e-9
    season_wide = compute_opp_dvp_map(logs)["SEA"]
    assert abs(by[("2026-05-03", 1)]["opp_dvp_forward"] - season_wide) > 1e-6
    # Opponent with no prior games at all stays 0.0.
    assert by[("2026-05-03", 2)]["opp_dvp_forward"] == 0.0
    # Opponent matching is case-insensitive, like the legacy map lookup.
    assert abs(by[("2026-05-03", 3)]["opp_dvp_forward"] - expected) < 1e-9
    for col in ("opp_dvp_guard", "opp_dvp_center"):
        assert by[("2026-05-03", 1)][col] == by[("2026-05-03", 1)]["opp_dvp_forward"]
    assert len(result) == 4
    assert "_dvp" not in result.columns and "_dvp_opp" not in result.columns


def test_legacy_dvp_is_season_wide_when_causal_disabled() -> None:
    from wnba_oracle.features.game_features import compute_opp_dvp_map

    logs = _dated_game_logs()
    with patch("wnba_oracle.ingest.minutes_features.fetch_wnba_team_stats", return_value={}):
        result = _enrich_corpus_matchup(_dated_corpus(), logs, causal_dvp=False)

    season_wide = compute_opp_dvp_map(logs)["SEA"]
    row = result.filter(pl.col("player_id") == 1).sort("game_date").row(0, named=True)
    assert abs(row["opp_dvp_forward"] - season_wide) < 1e-9


def test_causal_dvp_without_game_date_keeps_zero_columns() -> None:
    corpus = _make_corpus()
    with patch("wnba_oracle.ingest.minutes_features.fetch_wnba_team_stats", return_value={}):
        result = _enrich_corpus_matchup(corpus, _make_game_logs(), causal_dvp=True)

    for col in ("opp_dvp_guard", "opp_dvp_forward", "opp_dvp_center"):
        assert all(v == 0.0 for v in result[col].to_list())


# -- point-in-time pace -------------------------------------------------------


def _dated_game_logs_for_pace() -> pl.DataFrame:
    """Two game dates with different possessions/pace profiles.
    On 05-01, both LVA and SEA play (same game from both sides).
    On 05-03, both teams play again.
    A causal 05-03 row should only see the 05-01 game.
    """
    base = {
        "oreb": 1.0,
        "dreb": 5.0,
        "pts": 20.0,
        "reb": 6.0,
        "ast": 3.0,
        "stl": 1.0,
        "blk": 0.5,
        "tov": 1.0,
        "fgm": 7.0,
        "fga": 14.0,
        "fg3m": 1.0,
        "ftm": 5.0,
        "fta": 6.0,
    }
    return pl.DataFrame(
        [
            # Early game: LVA high FGA, high TOV -> higher possessions
            {"game_date": "2026-05-01", "team": "LVA", "opponent": "SEA", "min": 200.0, **base},
            # Early game: SEA (same opponent in same game)
            {"game_date": "2026-05-01", "team": "SEA", "opponent": "LVA", "min": 200.0, **base},
            # Later game: LVA low FGA, low TOV -> lower possessions
            {
                "game_date": "2026-05-03",
                "team": "LVA",
                "opponent": "SEA",
                "min": 200.0,
                "fga": 8.0,
                "tov": 0.0,
                **{k: v for k, v in base.items() if k not in ("fga", "tov")},
            },
            # Later game: SEA
            {
                "game_date": "2026-05-03",
                "team": "SEA",
                "opponent": "LVA",
                "min": 200.0,
                "fga": 8.0,
                "tov": 0.0,
                **{k: v for k, v in base.items() if k not in ("fga", "tov")},
            },
        ]
    )


def _dated_corpus_for_pace() -> pl.DataFrame:
    return pl.DataFrame(
        [
            {"game_date": "2026-05-01", "team": "LVA", "opponent": "SEA", "player_id": 1},
            {"game_date": "2026-05-03", "team": "LVA", "opponent": "SEA", "player_id": 1},
        ]
    )


def test_causal_pace_uses_only_strictly_prior_games() -> None:
    """Future games cannot affect a row's pace value.

    A row on 05-03 should see only games from 05-01 (and earlier), not its own
    05-03 game. If we remove the 05-03 game from logs, the 05-03 row's pace must
    remain identical -- that's the proof no future data leaked in.
    """
    logs_full = _dated_game_logs_for_pace()
    logs_prior = logs_full.filter(pl.col("game_date") < "2026-05-03")
    corpus = _dated_corpus_for_pace()

    # Build with full logs (including 05-03 game).
    with patch("wnba_oracle.ingest.minutes_features.fetch_wnba_team_stats", return_value={}):
        result_full = _enrich_corpus_matchup(corpus, logs_full, causal_pace=True)

    # Build with only prior games (no 05-03).
    with patch("wnba_oracle.ingest.minutes_features.fetch_wnba_team_stats", return_value={}):
        result_prior = _enrich_corpus_matchup(corpus, logs_prior, causal_pace=True)

    # 05-03 row's pace must be identical in both cases (future game did not affect it).
    row_full = result_full.filter(pl.col("game_date") == "2026-05-03").row(0, named=True)
    row_prior = result_prior.filter(pl.col("game_date") == "2026-05-03").row(0, named=True)

    assert abs(row_full["team_pace"] - row_prior["team_pace"]) < 1e-9, (
        f"05-03 row pace changed when 05-03 game was removed from logs: "
        f"with_future={row_full['team_pace']}, prior_only={row_prior['team_pace']}"
    )
    assert abs(row_full["opp_pace"] - row_prior["opp_pace"]) < 1e-9
    assert abs(row_full["game_pace_implied"] - row_prior["game_pace_implied"]) < 1e-9


def test_causal_pace_first_game_has_no_prior_data() -> None:
    """First appearance of a team gets fallback pace (0.0 when no prior games)."""
    logs = _dated_game_logs_for_pace()
    corpus = _dated_corpus_for_pace()

    with patch("wnba_oracle.ingest.minutes_features.fetch_wnba_team_stats", return_value={}):
        result = _enrich_corpus_matchup(corpus, logs, causal_pace=True)

    # 05-01 row is the first appearance: no prior games exist.
    row_first = result.filter(pl.col("game_date") == "2026-05-01").row(0, named=True)
    assert row_first["team_pace"] == 0.0, "First game should have 0 pace (no prior data)"
    assert row_first["opp_pace"] == 0.0, "First opponent should have 0 pace"


def test_causal_pace_populates_second_game() -> None:
    """Second game can see the first game's pace."""
    logs = _dated_game_logs_for_pace()
    corpus = _dated_corpus_for_pace()

    with patch("wnba_oracle.ingest.minutes_features.fetch_wnba_team_stats", return_value={}):
        result = _enrich_corpus_matchup(corpus, logs, causal_pace=True)

    # 05-03 row can now see 05-01 game, so pace should be non-zero.
    row_second = result.filter(pl.col("game_date") == "2026-05-03").row(0, named=True)
    assert row_second["team_pace"] > 0.0, "Second game should have computed pace from first game"
    assert row_second["opp_pace"] > 0.0, "Opponent pace should also be computed"
    assert row_second["game_pace_implied"] > 0.0


def test_legacy_pace_snapshot_when_causal_disabled() -> None:
    """When causal_pace=False, falls back to nba_api snapshot (old behavior)."""
    corpus = _make_corpus()
    game_logs = _make_game_logs()
    with patch(
        "wnba_oracle.ingest.minutes_features.fetch_wnba_team_stats",
        return_value=_FAKE_TEAM_STATS,
    ):
        result = _enrich_corpus_matchup(corpus, game_logs, causal_pace=False)

    # Should use nba_api snapshot values (same as before the fix).
    lva_rows = result.filter(pl.col("team") == "LVA")
    assert all(v == 90.0 for v in lva_rows["team_pace"].to_list())


def test_causal_pace_handles_case_insensitivity() -> None:
    """Team name matching is case-insensitive."""
    logs = pl.DataFrame(
        [
            {
                "game_date": "2026-05-01",
                "team": "lva",  # lowercase
                "opponent": "sea",  # lowercase
                "min": 200.0,
                "fga": 14.0,
                "oreb": 1.0,
                "tov": 1.0,
                "fta": 6.0,
            }
        ]
    )
    corpus = pl.DataFrame(
        [
            {
                "game_date": "2026-05-03",
                "team": "LVA",
                "opponent": "SEA",
                "player_id": 1,
            },  # uppercase
        ]
    )

    with patch("wnba_oracle.ingest.minutes_features.fetch_wnba_team_stats", return_value={}):
        result = _enrich_corpus_matchup(corpus, logs, causal_pace=True)

    # Should match despite case difference.
    row = result.row(0, named=True)
    assert row["team_pace"] > 0.0, "Case-insensitive team matching failed"
