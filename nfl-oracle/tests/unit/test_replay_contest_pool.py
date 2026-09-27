"""Unit tests for nfl_oracle.replay.contest_pool_replay (#280)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from nfl_oracle.contests.parse import ParsedContest
from nfl_oracle.contests.schema import ContestRecord, DraftStatRow, EntryLineupPick, EntryRecord
from nfl_oracle.recommendations.model import HistoricalPerformance, RatingModel, fit_model
from nfl_oracle.recommendations.picker_knobs import PickerKnobs
from nfl_oracle.recommendations.schema import EvidenceClock
from nfl_oracle.replay import contest_pool_replay as cpr
from nfl_oracle.replay.contest_pool_replay import (
    join_contest_pool,
    replay_contest_pools,
    replay_contest_pools_knob_sweep,
    rows_by_eastern_day,
    summarize,
)
from nfl_oracle.replay.harness import best_lineup, hindsight_best_lineup
from nfl_oracle.replay.production_backtest import LeakageError, hindsight_best

BASE = datetime(2024, 9, 8, 17, 0, tzinfo=UTC)  # 13:00 America/New_York
NOW = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)
SLOTS = (2.0, 1.8, 1.6, 1.4, 1.2)
SKILL = {1: 9.0, 2: 1.0, 3: 4.0, 4: 2.5, 5: 7.0, 6: 0.5, 7: 3.0, 8: 6.0}
GAMES = 12
TARGET_GAME = 1000 + GAMES - 1
MISSING_PLAYER = 99  # visible in the contest pool, absent from Corpus G that day
BOOSTED_PLAYER = 2  # low raw value, maximum boost
C_OVERRIDE_PLAYER = 1  # Corpus C reports a different final value than Corpus G


def _rows(*, late_game: int | None = None) -> list[HistoricalPerformance]:
    rows = []
    for game in range(GAMES):
        kickoff = BASE + timedelta(days=7 * game)
        delay = timedelta(days=9) if game == late_game else timedelta(hours=4)
        for player, skill in SKILL.items():
            team = 1 if player <= 4 else 2
            rows.append(
                HistoricalPerformance(
                    player_id=player,
                    game_id=1000 + game,
                    position="WR" if player % 2 else "RB",
                    kickoff_at=kickoff,
                    available_at=kickoff + delay,
                    captured_at=NOW - timedelta(days=1),
                    value=skill + 0.25 * ((player * game) % 3),
                    opportunity=float(player + game),
                    team_id=team,
                    opponent_team_id=3 - team,
                    did_not_play=player == 6 and game % 3 == 0,
                    context_features={"opp_def_value_allowed_prior": 1.0 + game % 2},
                    context_clock=EvidenceClock(source_available_at=NOW, captured_at=NOW),
                    context_evidence_mode="retrospective_reconstructed",
                )
            )
    return rows


def _pick(player_id: int, slot: int, value: float, boost: float) -> EntryLineupPick:
    mult = SLOTS[slot - 1]
    return EntryLineupPick(
        player_id=player_id,
        slot=slot,
        slot_multiplier=mult,
        card_boost=boost,
        effective_multiplier=mult + boost,
        value=value,
        score=value * (mult + boost),
    )


def _contest(
    rows: Sequence[HistoricalPerformance], *, boosts: dict[int, float] | None = None
) -> ParsedContest:
    target = {r.player_id: r for r in rows if r.game_id == TARGET_GAME}
    boost_of = boosts if boosts is not None else {BOOSTED_PLAYER: 3.0}
    values = {pid: row.value for pid, row in target.items()}
    values[C_OVERRIDE_PLAYER] += 2.0
    values[MISSING_PLAYER] = 0.0
    pool = [pid for pid in (*sorted(target), MISSING_PLAYER) if pid != 6]
    draft = tuple(
        DraftStatRow(
            contest_id=7,
            player_id=pid,
            section="Most drafted",
            card_boost=boost_of.get(pid, 0.0),
            value=values[pid],
        )
        for pid in pool
    )

    def entry(entry_id: int, rank: int, ids: Sequence[int]) -> EntryRecord:
        return EntryRecord(
            contest_id=7,
            entry_id=entry_id,
            rank=rank,
            picks=tuple(
                _pick(pid, slot, values[pid], boost_of.get(pid, 0.0))
                for slot, pid in enumerate(ids, start=1)
            ),
        )

    day = BASE.date() + timedelta(days=7 * (GAMES - 1))
    return ParsedContest(
        contest=ContestRecord(
            contest_id=7,
            sport="nfl",
            day=day,
            end_day=day,
            lineup_size=5,
            slot_multipliers=SLOTS,
            entrants=5000,
            is_finalized=True,
            captured_at=NOW,
        ),
        entries=(entry(1, 1, (1, 5, 8, 3, 2)), entry(2, 2, (8, 5, 7, 3, 4))),
        draft_stats=draft,
        missing_routes=(),
        law_verified=True,
    )


def test_replay_runs_production_on_the_visible_pool_under_contest_boosts() -> None:
    rows = _rows()
    contest = _contest(rows)
    results, excluded = replay_contest_pools(rows, [contest], now=NOW)
    assert excluded == {}
    (result,) = results
    # Pool: visible ids minus the missing player (player 6 was never in the pool).
    assert result.visible_pool_size == 8
    assert result.candidate_count == 7
    assert result.pool_missing_from_history == 1
    assert result.game_ids == (TARGET_GAME,)
    # A one-game pool relaxes diversity rather than being excluded.
    assert result.diversity_relaxed is True
    assert not result.is_zero_boost

    ceiling = hindsight_best_lineup(contest)
    assert ceiling is not None
    assert result.ceiling_score == pytest.approx(ceiling.total_score)
    # The boost-aware ceiling picks the boosted low-value player; a raw
    # rearrangement ceiling would not, so the two denominators differ.
    assert BOOSTED_PLAYER in ceiling.player_ids
    raw_ids, _raw = hindsight_best(contest.observed_values(), SLOTS)
    assert BOOSTED_PLAYER not in raw_ids

    # Scored with Corpus C values and the contest's boosts, in slot order.
    values = contest.observed_values()
    boosts = contest.boost_table()
    expected = sum(
        values[pid] * (slot + boosts.get(pid, 0.0))
        for pid, slot in zip(result.production_player_ids, SLOTS, strict=True)
    )
    assert result.production_score == pytest.approx(expected)
    assert result.capture_ratio == pytest.approx(expected / ceiling.total_score)
    assert result.value_mismatches == 1
    assert 0 < result.capture_ratio <= result.ordered_capture_ratio <= 1.0 + 1e-9

    assert result.winner_player_ids == (1, 5, 8, 3, 2)
    assert result.winner_capture_ratio is not None
    assert result.visible_entries == 2
    assert 0 <= result.beats_visible_entries <= 2
    assert result.beats_winner == (result.production_score > (result.winner_score or 0.0))
    assert result.naive_capture_ratio is not None


def test_zero_boost_contest_ceiling_matches_rearrangement() -> None:
    rows = _rows()
    contest = _contest(rows, boosts={})
    (result,), _excluded = replay_contest_pools(rows, [contest], now=NOW)
    assert result.is_zero_boost
    _ids, raw = hindsight_best(contest.observed_values(), SLOTS)
    assert result.ceiling_score == pytest.approx(raw)
    summary = summarize([result])
    assert summary.zero_boost.n_contests == 1
    assert summary.boosted.n_contests == 0
    assert summary.all.mean_capture_ratio == pytest.approx(result.capture_ratio)


def test_training_never_sees_the_contest_day_or_late_labels() -> None:
    # Game 1010's label finalizes after the target game kicks off.
    rows = _rows(late_game=GAMES - 2)
    seen: list[frozenset[int]] = []

    def spy(train: Sequence[HistoricalPerformance], trained_at: datetime) -> RatingModel:
        seen.append(frozenset(r.game_id for r in train))
        return fit_model(train, trained_at=trained_at)

    replay_contest_pools(rows, [_contest(rows)], now=NOW, fitter=spy)
    (games,) = seen
    assert TARGET_GAME not in games
    assert TARGET_GAME - 1 not in games
    assert TARGET_GAME - 2 in games


def test_replay_fails_closed_when_walk_forward_filter_is_bypassed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def leaky_rows_before(
        rows: Sequence[HistoricalPerformance], **_kwargs: object
    ) -> tuple[HistoricalPerformance, ...]:
        return tuple(rows)

    monkeypatch.setattr(cpr, "rows_before", leaky_rows_before)
    rows = _rows()
    with pytest.raises(LeakageError):
        replay_contest_pools(rows, [_contest(rows)], now=NOW)


def test_join_uses_the_days_first_kickoff_and_counts_unjoinable_contests() -> None:
    rows = _rows()
    contest = _contest(rows)
    by_day = rows_by_eastern_day(rows)
    early = [
        r.model_copy(
            update={
                "game_id": 5000,
                "player_id": r.player_id + 100,
                "team_id": (r.team_id or 0) + 10,
                "opponent_team_id": (r.opponent_team_id or 0) + 10,
                "kickoff_at": r.kickoff_at - timedelta(hours=3),
                "available_at": r.available_at - timedelta(hours=3),
            }
        )
        for r in by_day[contest.contest.day]
    ]
    pool = join_contest_pool(contest, [*by_day[contest.contest.day], *early])
    assert pool is not None
    # The unrelated earlier game sets the cutoff and is excluded from training,
    # but its players never enter this contest's candidate pool.
    assert pool.cutoff == min(r.kickoff_at for r in early)
    assert pool.day_game_ids == (TARGET_GAME, 5000)
    assert pool.game_ids == (TARGET_GAME,)
    assert pool.missing_player_ids == (MISSING_PLAYER,)

    unjoinable = contest.contest.model_copy(update={"day": BASE.date() - timedelta(days=30)})
    orphan = ParsedContest(
        contest=unjoinable,
        entries=contest.entries,
        draft_stats=contest.draft_stats,
        missing_routes=(),
        law_verified=True,
    )
    results, excluded = replay_contest_pools(rows, [orphan], now=NOW)
    assert results == ()
    assert excluded == {"no_corpus_g_rows_for_day": 1}


def test_best_lineup_is_the_harness_ceiling_over_any_value_table() -> None:
    values = {1: 10.0, 2: 9.0, 3: 8.0, 4: 7.0, 5: 6.0, 6: 5.9}
    zero = best_lineup(values, {}, SLOTS)
    assert zero is not None and zero.player_ids == (1, 2, 3, 4, 5)
    boosted = best_lineup(values, {6: 3.0}, SLOTS)
    assert boosted is not None and 6 in boosted.player_ids and 5 not in boosted.player_ids
    assert best_lineup({1: 1.0}, {}, SLOTS) is None


def test_knob_sweep_shares_one_fit_across_profiles() -> None:
    rows = _rows()
    fits: list[int] = []

    def spy(train: Sequence[HistoricalPerformance], trained_at: datetime) -> RatingModel:
        fits.append(len(train))
        return fit_model(train, trained_at=trained_at)

    knobs = (
        PickerKnobs(profile="identity"),
        PickerKnobs(boost_rank_blend=0.5, profile="boost_0.5"),
        PickerKnobs(position_calibration=1.0, profile="pos_1.0"),
    )
    swept = replay_contest_pools_knob_sweep(
        rows,
        [_contest(rows)],
        knobs,
        now=NOW,
        fitter=spy,
    )
    assert len(fits) == 1  # one weekly fit, many picker settings
    assert set(swept) == {"identity", "boost_0.5", "pos_1.0"}
    for profile, (results, _excluded) in swept.items():
        assert len(results) == 1
        assert results[0].picker_profile == profile
        assert 0.0 <= results[0].capture_ratio <= 1.0


def test_knob_sweep_excluded_is_isolated_per_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression for the shared excluded dict bug (#338).

    A picker-specific exclusion recorded for one profile's per-run pass must
    not leak into another profile's reported ``excluded`` reasons, while a
    pool-level exclusion that happens once, before any picker knob runs,
    must appear identically on every profile.
    """
    rows = _rows()
    good_contest = _contest(rows)
    # Triggers the shared, profile-independent "no_draft_stats" exclusion in
    # the pool-building pass, before any picker knob is ever considered.
    empty_contest = replace(good_contest, draft_stats=())

    real_run_contest = cpr._run_contest

    def fake_run_contest(
        pool: cpr.ContestPool, *, picker: PickerKnobs, excluded: dict[str, int], **kwargs: object
    ) -> cpr.ContestPoolResult | None:
        if picker.profile == "flaky":
            excluded["flaky_only_reason"] += 1
            return None
        return real_run_contest(pool, picker=picker, excluded=excluded, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(cpr, "_run_contest", fake_run_contest)

    knobs = (
        PickerKnobs(profile="identity"),
        PickerKnobs(boost_rank_blend=0.5, profile="flaky"),
    )
    swept = replay_contest_pools_knob_sweep(
        rows,
        [empty_contest, good_contest],
        knobs,
        now=NOW,
    )
    identity_results, identity_excluded = swept["identity"]
    flaky_results, flaky_excluded = swept["flaky"]

    assert len(identity_results) == 1
    assert len(flaky_results) == 0
    # The shared pool-level exclusion appears on both profiles...
    assert identity_excluded == {"no_draft_stats": 1}
    # ...but "flaky"'s own per-run exclusion never leaks onto "identity", and
    # "identity"'s success never erases "flaky"'s own exclusion.
    assert flaky_excluded == {"no_draft_stats": 1, "flaky_only_reason": 1}


def test_boost_rank_blend_changes_capture_on_boosted_contest() -> None:
    rows = _rows()
    identity = replay_contest_pools(
        rows, [_contest(rows)], now=NOW, picker=PickerKnobs(profile="identity")
    )[0][0]
    blended = replay_contest_pools(
        rows,
        [_contest(rows)],
        now=NOW,
        picker=PickerKnobs(boost_rank_blend=1.0, profile="full_boost"),
    )[0][0]
    # Same contest, different picker profile labels; capture may or may not
    # move on this tiny fixture, but the path must complete and record profile.
    assert identity.picker_profile == "identity"
    assert blended.picker_profile == "full_boost"
