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
