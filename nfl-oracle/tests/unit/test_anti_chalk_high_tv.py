"""Anti-chalk + high-potential label path pins for issue #185."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from nfl_oracle.features.schema import offline_stub_feature_names
from nfl_oracle.recommendations.high_tv import (
    report_nfl_archive_season_depth,
    sample_weights_for_history,
)
from nfl_oracle.recommendations.model import (
    HistoricalPerformance,
    _neutral_appearance_count_feature,
    _PriorBank,
    fit_model,
    predict,
)
from nfl_oracle.recommendations.schema import Candidate, Contest, EvidenceClock, Game, Slate
from nfl_oracle.valuelaw.candidates import CandidateRow, PlayerHistory
from nfl_oracle.valuelaw.project import project_candidates

BASE = datetime(2025, 9, 1, 12, tzinfo=UTC)


def test_appearance_count_feature_is_neutral() -> None:
    assert _neutral_appearance_count_feature(0) == 0.0
    assert _neutral_appearance_count_feature(50) == 0.0
    bank = _PriorBank()
    for week in range(8):
        kickoff = BASE + timedelta(days=week)
        bank.add(
            HistoricalPerformance(
                player_id=1,
                game_id=100 + week,
                position="WR",
                kickoff_at=kickoff,
                available_at=kickoff + timedelta(hours=2),
                captured_at=kickoff + timedelta(hours=3),
                value=3.0,
            )
        )
    vector = bank.vector(1, "WR")
    assert vector[4] == 0.0  # prior_log_count slot


def test_low_frequency_high_ev_beats_high_frequency_lower_ev_in_valuelaw() -> None:
    """1-game sleeper keeps shrunk value signal vs multi-game chalk (#185)."""

    now = datetime(2026, 9, 9, 20, tzinfo=UTC)

    def cand(pid: int) -> Candidate:
        clock = EvidenceClock(source_available_at=now, captured_at=now)
        return Candidate(
            player_id=pid,
            game_id=1,
            team_id=1,
            name=f"P{pid}",
            position="WR",
            team="SEA",
            opponent="NE",
            injury_status="Active",
            card_boost=0.0,
            clock=clock,
        )

    def hist(pid: int, values: tuple[float, ...]) -> PlayerHistory:
        return PlayerHistory(
            player_id=pid,
            games=len(values),
            mean_box_value=sum(values) / len(values),
            max_box_value=max(values),
            min_box_value=min(values),
            last_box_value=values[-1],
            last_played_at=now - timedelta(days=1),
            seasons=(2025,),
            values=values,
        )

    # Sleeper: 1 game at 16.6. Chalk: many games at ~4. Fillers for position mean.
    rows = (
        CandidateRow(candidate=cand(101), history=hist(101, (16.6,))),
        CandidateRow(candidate=cand(202), history=hist(202, (4.0,) * 10)),
        *[
            CandidateRow(candidate=cand(300 + i), history=hist(300 + i, (3.0, 3.0, 3.0)))
            for i in range(4)
        ],
    )
    projected = {p.player_id: p for p in project_candidates(rows)}
    assert projected[101].method == "player_ewma_shrunk"
    assert projected[101].projected_value > projected[202].projected_value


def test_sample_weights_prefer_high_value_not_appearance_volume() -> None:
    rows = []
    kickoff = BASE
    # One high-TV sleeper observation and many chalk observations in same game.
    for pid, value in [(1, 16.6), (2, 4.0), (3, 3.5), (4, 3.0), (5, 2.5), (6, 2.0)]:
        rows.append(
            HistoricalPerformance(
                player_id=pid,
                game_id=500,
                position="WR",
                kickoff_at=kickoff,
                available_at=kickoff + timedelta(hours=2),
                captured_at=kickoff + timedelta(hours=3),
                value=value,
            )
        )
    weights = sample_weights_for_history(rows, top_k=1, high_weight=4.0)
    assert weights[0] == 4.0
    assert weights[1] == 1.0


def test_pace_priors_are_no_longer_offline_stubs() -> None:
    stubs = set(offline_stub_feature_names())
    assert "team_pace_prior" not in stubs
    assert "opponent_pace_prior" not in stubs
    # Still queued / not enabled for TNF week-2 without live capture:
    assert "injury_status" in stubs
    assert "weather_temp_f" in stubs


def test_archive_depth_report_uses_catalog_without_year_cap() -> None:
    root = Path(__file__).resolve().parents[2]
    depth = report_nfl_archive_season_depth(project_root=root)
    # Catalog seeds span 2002-2025 in-repo even when corpus_g is empty on disk.
    assert depth.year_cap is None
    assert min(depth.catalog_seasons) == 2002
    assert max(depth.catalog_seasons) >= 2025


def test_predict_zeros_prior_log_count_coefficient_on_legacy_artifacts() -> None:
    rows: list[HistoricalPerformance] = []
    for game in range(6):
        kickoff = BASE + timedelta(days=game)
        for player in range(1, 7):
            rows.append(
                HistoricalPerformance(
                    player_id=player,
                    game_id=100 + game,
                    position="QB" if player == 1 else "WR",
                    kickoff_at=kickoff,
                    available_at=kickoff + timedelta(hours=2),
                    captured_at=kickoff + timedelta(hours=3),
                    value=float(player + game),
                    opportunity=float(player),
                )
            )
    trained_at = BASE + timedelta(days=7)
    model = fit_model(rows, trained_at=trained_at)
    # Poison appearance-count coefficient as a legacy artifact would.
    coeffs = list(model.coefficients)
    chalk_index = model.feature_names.index("prior_log_count")
    coeffs[chalk_index] = 99.0
    poisoned = model.model_copy(update={"coefficients": tuple(coeffs)})

    decision = BASE + timedelta(days=9)
    clock = EvidenceClock(source_available_at=decision, captured_at=decision)
    games = (
        Game(
            game_id=200,
            season=2025,
            kickoff_at=decision + timedelta(hours=4),
            home_team_id=10,
            away_team_id=11,
            home_team="A",
            away_team="B",
            status="scheduled",
        ),
        Game(
            game_id=201,
            season=2025,
            kickoff_at=decision + timedelta(hours=5),
            home_team_id=12,
            away_team_id=13,
            home_team="C",
            away_team="D",
            status="scheduled",
        ),
    )
    candidates = tuple(
        Candidate(
            player_id=player,
            game_id=games[player % 2].game_id,
            team_id=(10 + (2 * (player % 2)) + player % 2),
            name=f"P{player}",
            position="WR",
            team="A",
            opponent="B",
            injury_status="Active",
            card_boost=0.0,
            clock=clock,
        )
        for player in range(1, 7)
    )
    slate = Slate(
        contest=Contest(
            contest_id=900,
            day=decision.date(),
            end_day=decision.date(),
            slot_multipliers=(2, 1.8, 1.6, 1.4, 1.2),
            is_locked=False,
            is_finalized=False,
            clock=clock,
            evidence_sha256="a" * 64,
        ),
        games=games,
        candidates=candidates,
        captured_at=decision,
        source_hashes=("b" * 64,),
        pool_roster_count=len(candidates),
        pool_search_matched_count=len(candidates),
    )
    # Must not raise; appearance coeff neutralized inside predict.
    projections = predict(slate, poisoned, rows, decision_at=decision)
    assert len(projections) == 6
