"""Pure-computation tests for the issue #37 field-intelligence study script."""

from __future__ import annotations

import importlib.util
import json
import math
import pathlib
import sys
from types import ModuleType

import pandas as pd
import pytest

SCRIPT = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "analyze_field_intelligence.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("analyze_field_intelligence", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


afi = _load_script()


def _pick(order: int, pid: int, value: float, base: float, bonus: float) -> dict:
    return {
        "order": order,
        "playerId": pid,
        "value": str(value),
        "multiplier": base + bonus,
        "multiplierBonus": bonus,
    }


def _lineup(pids: list[int], values: list[float], boosts: list[float]) -> str:
    bases = afi.SLOT_BASES
    return json.dumps([_pick(i, pids[i], values[i], bases[i], boosts[i]) for i in range(5)])


def _labels(slates: int = 3, players: int = 10) -> pd.DataFrame:
    rows = []
    for s in range(slates):
        for p in range(players):
            rows.append(
                {
                    "slate_date": f"2026-06-{10 + s:02d}",
                    "section": "popularPlayers" if p % 2 else "highestBoostedValuePlayers",
                    "platform_player_id": p,
                    "team_key": f"T{p % 4}",
                    # boost falls as drafts rise (the platform mechanic).
                    "card_boost": round(3.0 - 0.3 * p, 2),
                    "drafts": float(100 * (p + 1)),
                    "real_score": 1.0 + 0.1 * p,
                }
            )
    return pd.DataFrame(rows)


# --- parse_lineup ---------------------------------------------------------


def test_parse_lineup_recovers_slot_base_from_multiplier_minus_bonus() -> None:
    raw = _lineup([1, 2, 3, 4, 5], [5, 4, 3, 2, 1], [0, 0.9, 2.3, 2.8, 3.0])
    picks = afi.parse_lineup(raw)
    assert [p["slot_base"] for p in picks] == list(afi.SLOT_BASES)
    assert picks[1]["boost"] == pytest.approx(0.9)
    assert picks[0]["value"] == pytest.approx(5.0)


def test_parse_lineup_sorts_by_order_field() -> None:
    raw = json.loads(_lineup([1, 2, 3, 4, 5], [5, 4, 3, 2, 1], [0] * 5))
    picks = afi.parse_lineup(list(reversed(raw)))
    assert [int(p["player_id"]) for p in picks] == [1, 2, 3, 4, 5]


@pytest.mark.parametrize(
    "raw",
    [json.dumps([]), json.dumps([_pick(0, 1, 1.0, 2.0, 0.0)] * 4), "not json"],
)
def test_parse_lineup_rejects_malformed(raw: str) -> None:
    with pytest.raises((ValueError, json.JSONDecodeError)):
        afi.parse_lineup(raw)


# --- pseudonymize / loaders ----------------------------------------------


def test_pseudonymize_is_stable_and_hides_input() -> None:
    token = afi.pseudonymize("some-user-slug")
    assert token == afi.pseudonymize("some-user-slug")
    assert "some-user-slug" not in token
    assert len(token) == 12


def test_load_leaderboards_drops_raw_user_id(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "lb.csv"
    pd.DataFrame(
        [
            {
                "slate_date": "2026-06-10",
                "rank": 1,
                "user_id": "abc",
                "score": 50.0,
                "lineup": _lineup([1, 2, 3, 4, 5], [1] * 5, [0] * 5),
            }
        ]
    ).to_csv(path, index=False)
    df = afi.load_leaderboards(path)
    assert "user_id" not in df.columns
    assert df.loc[0, "user_token"] == afi.pseudonymize("abc")


def test_loaders_fail_on_missing_columns(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "bad.csv"
    pd.DataFrame([{"slate_date": "2026-06-10"}]).to_csv(path, index=False)
    with pytest.raises(ValueError, match="missing columns"):
        afi.load_labels(path)
    with pytest.raises(ValueError, match="missing columns"):
        afi.load_leaderboards(path)


def test_load_json_dir_skips_404_bodies_and_bad_json(tmp_path: pathlib.Path) -> None:
    (tmp_path / "2026-06-10.json").write_text(json.dumps({"slate_date": "2026-06-10"}))
    (tmp_path / "2026-06-11.json").write_text(json.dumps({"detail": "no dossier for slate"}))
    (tmp_path / "2026-06-12.json").write_text("{broken")
    assert set(afi.load_json_dir(tmp_path)) == {"2026-06-10"}


# --- stats helpers --------------------------------------------------------


def test_spearman_nan_on_degenerate_input() -> None:
    assert math.isnan(afi.spearman([1, 1, 1], [1, 2, 3]))
    assert math.isnan(afi.spearman([1, 2], [1, 2]))
    assert afi.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)


def test_bootstrap_ci_brackets_mean_and_ignores_nan() -> None:
    mean, lo, hi = afi.bootstrap_ci([1.0, 2.0, 3.0, float("nan")])
    assert mean == pytest.approx(2.0)
    assert lo <= mean <= hi
    assert all(math.isnan(v) for v in afi.bootstrap_ci([]))


@pytest.mark.parametrize(("teams", "cap"), [(2, 5), (4, 3), (6, 2), (12, 2)])
def test_effective_team_cap_mirrors_dynamic_cap(teams: int, cap: int) -> None:
    assert afi.effective_team_cap(teams) == cap


# --- realized ceiling -----------------------------------------------------


def test_realized_ceiling_respects_team_cap_and_orders_by_value() -> None:
    pool = pd.DataFrame(
        {
            "platform_player_id": [1, 2, 3, 4, 5, 6],
            "team_key": ["A", "A", "A", "B", "C", "D"],
            "real_score": [10.0, 9.0, 8.0, 1.0, 1.0, 1.0],
            "card_boost": [0.0] * 6,
        }
    )
    score, pids = afi.realized_ceiling(pool, cap=2)
    assert 3 not in pids  # third A player excluded by cap
    assert score == pytest.approx(10 * 2.0 + 9 * 1.8 + 1 * 1.6 + 1 * 1.4 + 1 * 1.2)
    uncapped, _ = afi.realized_ceiling(pool, cap=5)
    assert uncapped > score


def test_realized_ceiling_empty_when_pool_too_small() -> None:
    pool = _labels(1, 4)
    score, pids = afi.realized_ceiling(pool, cap=5)
    assert math.isnan(score)
    assert pids == []


# --- section A ------------------------------------------------------------


def test_audit_labels_flags_gaps_and_duplicates() -> None:
    labels = _labels(2, 6)
    late = _labels(1, 6).assign(slate_date="2026-07-01")
    dup = labels.iloc[[0]]
    audit = afi.audit_labels(pd.concat([labels, late, dup]), since="2026-06-01")
    assert audit["window_slates"] == 3
    assert audit["duplicate_player_rows"] == 1
    assert audit["calendar_gaps_over_3_days"][0]["before"] == "2026-07-01"
    assert audit["slates_below_ceiling_threshold"] == 3


def test_audit_leaderboards_counts_bad_lineups_and_missing_rank1() -> None:
    good = _lineup([1, 2, 3, 4, 5], [1] * 5, [0] * 5)
    lb = pd.DataFrame(
        {
            "slate_date": ["2026-06-10", "2026-06-10", "2026-06-11"],
            "rank": [1, 2, 3],
            "user_token": ["a", "b", "a"],
            "score": [10.0, 9.0, 8.0],
            "lineup": [good, "[]", good],
        }
    )
    audit = afi.audit_leaderboards(lb, since="2026-06-01")
    assert audit["unparseable_lineups"] == 1
    assert audit["slates_missing_rank1"] == 1
    assert audit["distinct_users"] == 2


# --- section B ------------------------------------------------------------


def test_estimator_alignment_detects_boost_sign_inversion() -> None:
    result = afi.estimator_alignment(_labels())
    # drafts rise while boost falls: the boost channel is perfectly inverted.
    assert result["drafts_vs_card_boost"][0] == pytest.approx(-1.0)
    assert result["drafts_vs_real_score"][0] == pytest.approx(1.0)
    assert result["n_slates"] == 3


def test_prior_slate_signal_uses_only_earlier_slates() -> None:
    labels = _labels(3, 8)
    out = afi.prior_slate_ownership_signal(labels)
    # first slate has no prior; the other two pair every player with the
    # previous slate, where drafts ranks are identical.
    assert out["n_pairs"] == 16
    assert out["n_slates"] == 2
    assert out["prior_slate_pct_vs_today_pct"][0] == pytest.approx(1.0)


def test_prior_slate_signal_never_pairs_a_slate_with_itself() -> None:
    labels = _labels(1, 8)
    out = afi.prior_slate_ownership_signal(labels)
    assert out["n_pairs"] == 0


def test_popularity_value_correlation_reports_each_section() -> None:
    out = afi.popularity_value_correlation(_labels(3, 12))
    assert {"all_sections_dedup", "popularPlayers", "highestBoostedValuePlayers"} <= set(out)
    assert out["all_sections_dedup"]["n_slates"] == 3


def test_ceiling_membership_prefers_low_drafts_when_boost_dominates() -> None:
    out = afi.ceiling_popularity_membership(_labels(2, 10))
    assert out["n_slates"] == 2
    assert out["member_drafts_pct_mean"][0] < 0.5


def test_slot_order_profile_zero_headroom_for_sorted_lineup() -> None:
    lb = pd.DataFrame({"lineup": [_lineup([1, 2, 3, 4, 5], [5, 4, 3, 2, 1], [0] * 5)]})
    prof = afi.slot_order_profile(lb)
    assert prof["n_entries"] == 1
    assert prof["share_zero_headroom"] == 1.0
    assert prof["top_slot_is_max_value"] == 1.0


def test_slot_order_profile_positive_headroom_for_reversed_lineup() -> None:
    lb = pd.DataFrame({"lineup": [_lineup([1, 2, 3, 4, 5], [1, 2, 3, 4, 5], [0] * 5), "[]"]})
    prof = afi.slot_order_profile(lb)
    assert prof["n_entries"] == 1  # malformed row skipped, not fatal
    assert prof["headroom"][0] > 0


def _leaderboard(slates: int, users: list[str]) -> pd.DataFrame:
    rows = []
    for s in range(slates):
        for r, u in enumerate(users, start=1):
            rows.append(
                {
                    "slate_date": f"2026-06-{10 + s:02d}",
                    "rank": r,
                    "user_token": u,
                    "score": 60.0 - r,
                    "lineup": _lineup([0, 1, 2, 3, 4], [5, 4, 3, 2, 1], [0.0] * 5),
                }
            )
    return pd.DataFrame(rows)


def test_repeat_finishers_gated_on_small_samples() -> None:
    out = afi.repeat_finisher_comparison(_leaderboard(3, ["a", "b"]), _labels())
    assert out["gated"] is True
    assert out["n_repeat_users"] == 2


def test_repeat_finishers_reports_when_groups_large_enough() -> None:
    lb = _leaderboard(3, ["r1", "r2"])
    once = pd.concat(
        [
            _leaderboard(1, [f"o{s}_{i}" for i in range(4)]).assign(
                slate_date=f"2026-06-{10 + s:02d}"
            )
            for s in range(3)
        ]
    )
    out = afi.repeat_finisher_comparison(
        pd.concat([lb, once]), _labels(), min_appearances=3, min_group=2
    )
    assert out["gated"] is False
    assert set(out["drafts_pct"]) == {"repeat_mean", "other_mean", "welch_t"}


def test_top20_duplication_counts_exact_mirrors() -> None:
    out = afi.top20_duplication(_leaderboard(2, ["a", "b", "c"]))
    assert out["exact_duplicate_share"][0] == pytest.approx(1.0)
    assert out["mean_pairwise_overlap"][0] == pytest.approx(5.0)


def test_ownership_skew_by_rank_bands_and_unobserved_share() -> None:
    lb = _leaderboard(1, ["a", "b"])
    lb.loc[1, "lineup"] = _lineup([90, 91, 92, 93, 94], [1] * 5, [0] * 5)
    out = afi.ownership_skew_by_rank(lb, _labels(1))
    band1 = out[out["band"] == "1"].iloc[0]
    band2 = out[out["band"] == "2-5"].iloc[0]
    assert band1["unobserved_share"] == 0.0
    assert band2["unobserved_share"] == 1.0


# --- section C ------------------------------------------------------------


def _dossier(committed: float, c_censor, field: float, ceiling: float) -> dict:
    return {
        "entries": {
            "committed": {"score": committed, "censor_reason": c_censor},
            "field_best": {"score": field, "censor_reason": None},
            "theoretical_ceiling": {"score": ceiling, "censor_reason": "incomplete_labels"},
        }
    }


def test_dossier_gap_summary_excludes_censored_committed() -> None:
    table = afi.dossier_gap_table(
        {
            "2026-06-10": _dossier(30.0, None, 60.0, 70.0),
            "2026-06-11": _dossier(10.0, "incomplete_labels", 50.0, 50.0),
        }
    )
    s = afi.dossier_gap_summary(table)
    assert s["n_dossiers"] == 2
    assert s["n_committed_exact"] == 1
    assert s["committed_share_of_winner"][0] == pytest.approx(0.5)
    assert s["winner_within_5pct_of_ceiling"] == pytest.approx(0.5)
    assert afi.dossier_gap_summary(pd.DataFrame()) == {"n": 0}


def test_serving_knob_history_reads_lineup_serving_knobs_without_defaults() -> None:
    lineups = {
        "2026-06-01": {"payout_regime": "top_20", "lineup": {"player_ids": [1]}},
        "2026-08-30": {
            "payout_regime": "top_20",
            "lineup": {
                "serving_knobs": {"leverage_weight": 0.28, "committed_order_objective": True}
            },
        },
    }
    hist = afi.serving_knob_history(lineups)
    assert hist["has_serving_knobs"].tolist() == [False, True]
    assert pd.isna(hist.loc[0, "leverage_weight"])  # not filled from code defaults
    summary = afi.summarize_knob_history(hist)
    assert summary["leverage_weight"] == [{"from": "2026-08-30", "value": 0.28}]
    assert summary["duplication_weight"] == "absent"


def test_winner_vs_own_distribution_skips_lineups_without_percentiles() -> None:
    gaps = afi.dossier_gap_table(
        {
            "2026-06-01": _dossier(30.0, None, 60.0, 70.0),
            "2026-06-02": _dossier(30.0, None, 40.0, 70.0),
        }
    )
    lineups = {
        "2026-06-01": {
            "lineup": {"lineup_score_p10": 20.0, "lineup_score_p50": 35.0, "lineup_score_p90": 50.0}
        },
        "2026-06-02": {"lineup": {"player_ids": [1]}},
        "2026-06-03": {
            "lineup": {"lineup_score_p10": 0.0, "lineup_score_p50": 0.0, "lineup_score_p90": 0.0}
        },
    }
    out = afi.winner_vs_own_distribution(gaps, lineups)
    assert out["n"] == 1
    assert out["share_winner_above_our_p90"] == 1.0
    assert out["winner_over_our_p90"][0] == pytest.approx(1.2)
    assert out["committed_below_our_p50"] == 1.0  # 30 < 35
    assert out["committed_below_our_p10"] == 0.0
    assert afi.winner_vs_own_distribution(gaps, {}) == {"n": 0}


def test_regime_split_labels_unrecorded() -> None:
    gaps = afi.dossier_gap_table(
        {
            "2026-06-01": _dossier(30.0, None, 60.0, 70.0),
            "2026-08-30": _dossier(40.0, None, 50.0, 60.0),
        }
    )
    hist = afi.serving_knob_history(
        {
            "2026-06-01": {"lineup": {}},
            "2026-08-30": {"lineup": {"serving_knobs": {"leverage_weight": 0.28}}},
        }
    )
    out = afi.regime_split(gaps, hist, "leverage_weight").set_index("leverage_weight")
    assert out.loc["unrecorded", "committed_share_of_winner"] == pytest.approx(0.5)
    assert out.loc["0.28", "committed_share_of_winner"] == pytest.approx(0.8)
