"""Model-validity audit (#53 umbrella): machine-readable characterization of
four training/serving facts that are easy to misstate from memory:

1. Pooled-F cohort truth -- despite G/F/C cohort scaffolding throughout
   features/spec.py and train/pipeline.py, every position value that reaches
   the trained heads (offline corpus AND live serve) is the literal string
   "F". G and C heads have never been trained or served with real data.
2. Write-only calibrators -- ``train_picker`` fits a ``PCHIPIsotonic``
   calibrator per (head, cohort) and stores it on the artifact, but no
   predict/serve code path ever calls ``.transform()`` on it. Calibration
   has zero effect on what a freeze actually serves.
3. Final-refit limitation -- ``train/cli.py`` trains the shipped artifact
   on the walk-forward (or fallback 80/20) TRAIN split only. It never
   refits on train+valid after picking the fold, so the most recent
   labeled rows (the held-out validation fold) are permanently excluded
   from the production model.
4. Train/serve feature parity -- MOSTLY holds: features/corpus.py (offline)
   and features/serving_features.py (live) both call the same
   ``features.rolling.build_rolling_features``, so rolling stats and
   ``days_rest`` agree for a shared player/date. Auditing it surfaced a
   real, previously undocumented gap: ``season_game_number`` -- a feature
   with a monotone constraint in train/models.yaml -- is *undercounted* in
   the training corpus relative to what serve computes for the identical
   player and date. Filed as
   https://github.com/cheeksmagunda/sports/issues/55 (fixing it is out of
   scope here: the culprit is features/corpus.py + features/game_features.py,
   outside train/, and a fix needs a full retrain per AGENTS.md's
   verification bar).

These are characterization tests: they assert CURRENT behavior so a future
change is a deliberate, visible decision (update this file + the model
validity audit issue together), not a silent regression.
"""

from __future__ import annotations

import sys
import typing
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from wnba_oracle.features.corpus import build_gamelog_corpus
from wnba_oracle.features.serving_features import build_head_feature_lookup
from wnba_oracle.features.spec import cohort_for_position
from wnba_oracle.scheduler.job2_model import _predict_heads_for_pool
from wnba_oracle.train import cli as train_cli
from wnba_oracle.train.pipeline import PickerArtifact, _filter_cohort, train_picker


def _multi_player_logs() -> pl.DataFrame:
    """Two players (one guard-caliber, one center-caliber by naming only --
    the corpus has no real position source) across a single season."""
    rows: list[dict] = []
    dates = [
        "2026-05-02",
        "2026-05-05",
        "2026-05-08",
        "2026-05-11",
        "2026-05-14",
        "2026-05-17",
    ]
    for pid, name, team in ((1, "A. Guardish", "SEA"), (2, "B. Centerish", "LVA")):
        for i, d in enumerate(dates):
            rows.append(
                {
                    "game_date": d,
                    "player_id": pid,
                    "player_name": name,
                    "team": team,
                    "season": "2026",
                    "min": 28.0 + i,
                    "pts": 14.0 + i,
                    "reb": 5.0,
                    "oreb": 1.0,
                    "dreb": 4.0,
                    "ast": 3.0,
                    "stl": 1.0,
                    "blk": 1.0,
                    "tov": 2.0,
                    "fgm": 6.0,
                    "fga": 12.0,
                    "fg3m": 1.0,
                    "ftm": 2.0,
                    "fta": 3.0,
                }
            )
    return pl.from_dicts(rows)


# --------------------------------------------------------------------------
# 1. Pooled-F cohort truth
# --------------------------------------------------------------------------


def test_gamelog_corpus_pools_every_player_into_cohort_f() -> None:
    """build_gamelog_corpus has no position source and hardcodes "F" for
    every row (features/corpus.py::build_gamelog_corpus). Two distinct
    players with no real position information both land in "F"."""
    corpus = build_gamelog_corpus(_multi_player_logs())
    assert not corpus.is_empty()
    assert set(corpus.get_column("position").unique().to_list()) == {"F"}


def test_filter_cohort_never_selects_g_or_c_from_the_real_gamelog_corpus() -> None:
    """Because every row's position is "F", filtering the heads corpus by
    the "G" or "C" cohort (what train_picker does per-cohort) always
    returns an empty frame -- those heads are architecturally never
    trained from build_gamelog_corpus output, regardless of the G/F/C
    scaffolding in train/pipeline.py and features/spec.py."""
    corpus = build_gamelog_corpus(_multi_player_logs())
    assert _filter_cohort(corpus, "G").is_empty()
    assert _filter_cohort(corpus, "C").is_empty()
    assert not _filter_cohort(corpus, "F").is_empty()


def test_cohort_for_position_pools_unknown_and_forward_together() -> None:
    """cohort_for_position's fallback ("return 'F'" for anything not
    starting with G or C) means blank/unrecognized Real Sports position
    strings are silently pooled with genuine forwards in the same cohort,
    on top of the corpus-level pooling above."""
    assert cohort_for_position("F") == "F"
    assert cohort_for_position("UNKNOWN") == "F"
    assert cohort_for_position(None) == "F"
    assert cohort_for_position("") == "F"


def test_serve_time_head_prediction_hardcodes_position_f_regardless_of_input() -> None:
    """job2_model._predict_heads_for_pool builds its prediction frame with a
    literal ``{"position": "F"}`` per row (see the D63-memory comment at its
    call site) -- it never reads a real position off the enrichment row, so
    this holds even when the enrichment dicts below carry no position field
    at all. This matches the pooled-F training above by construction."""
    captured: dict[str, list[str]] = {}

    class _FakeHead:
        feature_columns = ("mins_l10",)

    class _FakeArtifact:
        heads: typing.ClassVar[dict] = {
            ("minutes", "F"): _FakeHead(),
            ("real_score_per_min", "F"): _FakeHead(),
        }

        def predict_real_score(self, frame: pl.DataFrame) -> dict[str, np.ndarray]:
            captured["positions"] = frame.get_column("position").to_list()
            n = len(frame)
            return {
                "p10": np.full(n, 1.0),
                "p50": np.full(n, 2.0),
                "p90": np.full(n, 3.0),
            }

    enrichment = [
        {"real_sports_player_id": 100, "features_json": {"head_features": {"mins_l10": 10.0}}},
        {"real_sports_player_id": 200, "features_json": {"head_features": {"mins_l10": 20.0}}},
    ]
    out = _predict_heads_for_pool(_FakeArtifact(), enrichment)  # type: ignore[arg-type]
    assert set(out) == {100, 200}
    assert captured["positions"] == ["F", "F"]


# --------------------------------------------------------------------------
# 2. Write-only calibrators
# --------------------------------------------------------------------------


def _tiny_train_valid_frames() -> tuple[pl.DataFrame, pl.DataFrame]:
    """Enough rows (with a valid split) for train_picker to fit at least the
    F-cohort "minutes" and "real_score_per_min" heads plus a PCHIP
    calibrator, without paying for a full-size LightGBM run."""
    logs = _multi_player_logs()
    corpus = build_gamelog_corpus(logs)
    dates = sorted(corpus.get_column("game_date").unique().to_list())
    cut = max(1, int(len(dates) * 0.7))
    train_dates = set(dates[:cut])
    train_df = corpus.filter(pl.col("game_date").is_in(train_dates))
    valid_df = corpus.filter(~pl.col("game_date").is_in(train_dates))
    return train_df, valid_df


def test_calibrators_are_fitted_and_stored_on_the_artifact() -> None:
    train_df, valid_df = _tiny_train_valid_frames()
    art = train_picker(train_df, valid_df)
    assert len(art.calibrators) > 0, "expected at least one (head, cohort) calibrator"


def test_predict_real_score_never_invokes_the_stored_calibrators(monkeypatch) -> None:
    """The only serve-time consumer of a PickerArtifact, ``predict_real_score``,
    recomposes E[real_score] straight from the raw quantile-head predictions
    (see train/pipeline.py::PickerArtifact.predict_real_score). It never
    reads ``self.calibrators``. Poisoning ``PCHIPIsotonic.transform`` to
    raise proves a normal predict call never touches it -- the calibrators
    are written to the artifact/manifest but are dead weight at serve time."""
    from wnba_oracle.train.calibrators import PCHIPIsotonic

    train_df, valid_df = _tiny_train_valid_frames()
    art = train_picker(train_df, valid_df)
    assert len(art.calibrators) > 0

    def _poisoned_transform(self, x):
        raise AssertionError("PCHIPIsotonic.transform was called from a predict path")

    monkeypatch.setattr(PCHIPIsotonic, "transform", _poisoned_transform)

    frame = train_df.select(
        [c for c in train_df.columns if c not in ("minutes_played", "real_score_per_min")]
    )
    result = art.predict_real_score(frame)
    assert result is not None
    assert np.isfinite(result["p50"]).any()


# --------------------------------------------------------------------------
# 3. Final-refit limitation
# --------------------------------------------------------------------------


def test_cli_ships_an_artifact_trained_only_on_the_split_train_fold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """cli.main() picks a train/valid split (walk-forward, or the
    time-ordered 80/20 fallback used here with 5 dates -- fewer than
    WalkForwardSplitter needs to yield a fold) and calls
    ``train_picker(heads_train, heads_valid, ...)``. There is no later step
    that refits on heads_train + heads_valid once the split has served its
    purpose; the artifact that reaches production is missing the freshest
    labeled rows by construction."""
    dates = [f"2026-05-{d:02d}" for d in range(1, 6)]  # 5 unique dates
    heads_path = tmp_path / "heads.parquet"
    pl.DataFrame(
        {
            "game_date": dates,
            "minutes_played": [10.0, 12.0, 14.0, 16.0, 18.0],
        }
    ).write_parquet(heads_path)

    captured: dict[str, int] = {}

    def _fake_train_picker(train_df, valid_df, *, label_train=None, target_real_score="real_score"):
        captured["train_rows"] = len(train_df)
        captured["valid_rows"] = len(valid_df)
        return PickerArtifact(feature_module_sha="test", config={}, training_rows=len(train_df))

    monkeypatch.setattr(train_cli, "train_picker", _fake_train_picker)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "oracle-train",
            "--heads-corpus",
            str(heads_path),
            "--corpus-mode",
            "gamelog",
            "--artifact-dir",
            str(tmp_path / "models"),
            "--metrics-path",
            str(tmp_path / "metrics.json"),
        ],
    )

    rc = train_cli.main()
    assert rc == 0

    total_rows = len(dates)
    assert captured["valid_rows"] > 0, "test fixture must exercise a non-empty valid fold"
    assert captured["train_rows"] + captured["valid_rows"] == total_rows
    assert captured["train_rows"] < total_rows, (
        "the shipped artifact's training_rows must be strictly less than the "
        "full labeled corpus -- the held-out fold is never refit into the "
        "artifact that reaches production"
    )


# --------------------------------------------------------------------------
# 4. Train/serve feature parity -- mostly holds, one discovered gap
# --------------------------------------------------------------------------


def test_offline_corpus_and_live_serve_rolling_and_rest_features_agree() -> None:
    """features/corpus.py (offline, build_gamelog_corpus) and
    features/serving_features.py (live, build_head_feature_lookup) both
    delegate to features.rolling.build_rolling_features for the rolling
    stats, and compute an equivalent "days since last game" for days_rest.
    For the same player and as-of date they agree value-for-value -- this
    part of the corpus.py module docstring's parity claim holds."""
    logs = _multi_player_logs()
    corpus = build_gamelog_corpus(logs)
    dates = sorted(corpus.get_column("game_date").unique().to_list())
    target_date = dates[2]  # a mid-sequence date with real rolling history

    train_row = corpus.filter(
        (pl.col("game_date") == target_date) & (pl.col("player_id") == 1)
    ).row(0, named=True)

    lookup = build_head_feature_lookup(logs, slate_date=target_date)
    serve_row = lookup[1]  # indexed by nba_api player_id

    assert serve_row["mins_l5"] == pytest.approx(train_row["mins_l5"])
    assert serve_row["days_rest"] == pytest.approx(train_row["days_rest"])


def test_offline_corpus_season_game_number_undercounts_the_true_serve_time_value() -> None:
    """DISCOVERED BUG, tracked at
    https://github.com/cheeksmagunda/sports/issues/55 (out of scope to fix
    in this audit PR -- the culprit lives in features/corpus.py and
    features/game_features.py, outside train/).

    features/corpus.py::build_gamelog_corpus skips any calendar date whose
    ``build_rolling_features(as_of_date=d)`` comes back empty (true for a
    corpus's earliest date(s), since nobody yet has a prior game) --  that
    date's games never join into the corpus frame at all. Because
    ``add_schedule_features`` then computes ``season_game_number`` via
    ``cum_count()`` over the SURVIVING corpus rows (not the full game log),
    every player's training-time season_game_number is undercounted by the
    number of that player's leading dates the corpus dropped.

    features/serving_features.py::_schedule_for_player has no such gap: it
    counts prior games directly off the full raw game_logs table.

    This test locks the CURRENT (divergent) values so a silent fix does not
    slip in unnoticed -- when issue #55 is resolved, this test should be
    updated (not skipped) to assert the corrected, matching value on both
    paths.
    """
    logs = _multi_player_logs()
    corpus = build_gamelog_corpus(logs)
    dates = sorted(corpus.get_column("game_date").unique().to_list())
    target_date = dates[2]

    train_row = corpus.filter(
        (pl.col("game_date") == target_date) & (pl.col("player_id") == 1)
    ).row(0, named=True)
    lookup = build_head_feature_lookup(logs, slate_date=target_date)
    serve_row = lookup[1]

    # True chronological game number for player 1 at this date is 4
    # (2026-05-02, 05-05, 05-08, 05-11); serve gets it right, train does not.
    assert train_row["season_game_number"] == 3
    assert serve_row["season_game_number"] == 4
    assert train_row["season_game_number"] != serve_row["season_game_number"], (
        "train/serve season_game_number parity gap (issue #55) appears to be "
        "fixed -- update this test to assert equality instead of divergence"
    )
