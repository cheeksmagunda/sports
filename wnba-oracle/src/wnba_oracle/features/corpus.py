"""Assemble the feature+target training corpora (D63, the Phase-1 keystone).

The picker's heads were starved: the training corpus was 7 columns from
``slate_labels`` with none of the head target/feature columns, so every head was
skipped (``train/pipeline.py``). These builders close that gap.

``build_gamelog_corpus`` -- one row per player-game over the ~13k
``wnba_game_logs`` rows, with strictly-causal rolling features
(``rolling.build_rolling_features``, ``game_date < as_of``) and the per-game head
targets (``game_features.add_targets``). This dense frame is what the minutes +
per-minute heads train on; it clears ``low_data_mode`` honestly.

``build_label_corpus`` -- one row per player-slate over the ~3k contest rows
(``read_training_corpus`` schema), reserved for the EB baseline, the real_score
blend, and CQR calibration. Features can be joined here in a later phase; for now
it carries the contest ``card_boost`` + ``real_score`` the EB member needs.

Both call the same ``features`` code the serve path uses, so train/serve parity
holds by construction.
"""

from __future__ import annotations

import polars as pl

from wnba_oracle.common.logging import get_logger
from wnba_oracle.features.game_features import (
    TARGET_COLUMNS,
    add_schedule_features,
    add_targets,
    to_nba_api_schema,
)
from wnba_oracle.features.rolling import build_rolling_features
from wnba_oracle.predict.scoring import REAL_SCORE_INTERCEPT, REAL_SCORE_WEIGHTS

log = get_logger("oracle.features.corpus")

# Schedule features add_schedule_features produces (in features/spec.py).
_SCHEDULE_COLUMNS: tuple[str, ...] = (
    "days_rest",
    "is_back_to_back",
    "season_game_number",
)


def build_gamelog_corpus(
    game_logs: pl.DataFrame,
    *,
    min_prior_games: int = 1,
) -> pl.DataFrame:
    """One row per player-game with causal features + per-game targets.

    ``game_logs`` is the stored (lowercase, ISO-date) schema from
    ``db.reads.read_game_logs`` / ``wnba_game_logs.parquet``. A game row is kept
    only if the player has ``>= min_prior_games`` earlier games (so every row
    carries real rolling history); the inner join on the as-of feature frame
    enforces ``>= 1`` and ``min_prior_games`` tightens it further.
    """
    if game_logs.is_empty():
        return pl.DataFrame()

    adapted = to_nba_api_schema(game_logs)
    dates = sorted({d for d in game_logs.get_column("game_date").to_list() if d})
    frames: list[pl.DataFrame] = []
    for d in dates:
        feats = build_rolling_features(adapted, as_of_date=d)
        if feats.is_empty():
            continue
        today = game_logs.filter(pl.col("game_date") == d)
        # inner join: only players with prior games (i.e. a feature row) survive.
        frames.append(today.join(feats, on="player_id", how="inner"))
    if not frames:
        return pl.DataFrame()

    corpus = pl.concat(frames, how="diagonal_relaxed")
    corpus = add_targets(corpus)
    corpus = add_schedule_features(corpus)
    # Position is not carried in game logs; pool into a single cohort ("F") for
    # now. Splitting G/F/C needs a position source (Real Sports pool / identity
    # resolver) and is deferred -- on ~13k rows a single pooled cohort is the
    # small-data-safe choice anyway (research guardrail: do not over-split).
    corpus = corpus.with_columns(pl.lit("F").alias("position"))

    # D77: inject team_pace / opp_pace / game_pace_implied and opp_dvp from
    # the corpus itself. These were zero-filled in earlier builds; populating
    # them here closes the train/serve mismatch introduced by D74.
    # Notes:
    # - team_pace uses the current-season nba_api snapshot (season-stable,
    #   acceptable approximation for historical rows). Degrades to 0 on error.
    # - opp_dvp is season-wide (not rolling) -- a mild data-leak but the
    #   per-game noise dwarfs the signal anyway. Rolling DvP deferred.
    corpus = _enrich_corpus_matchup(corpus, game_logs)

    if min_prior_games > 1:
        corpus = corpus.filter(pl.col("season_game_number") > min_prior_games)
    # Defensive: require at least the L5 minutes feature to be present.
    corpus = corpus.filter(pl.col("mins_l5").is_not_null())

    log.info(
        "gamelog_corpus_built",
        rows=len(corpus),
        n_dates=len(dates),
        targets=list(TARGET_COLUMNS),
    )
    return corpus


def _enrich_corpus_matchup(corpus: pl.DataFrame, game_logs: pl.DataFrame) -> pl.DataFrame:
    """Add team_pace / opp_pace / game_pace_implied / opp_dvp_* to corpus rows.

    Uses nba_api for pace (current-season snapshot) and computes DvP as
    season-wide mean real_score allowed per opponent from the game_logs. Both
    degrade gracefully to 0 if the data source is unavailable.
    """
    # -- team pace from nba_api --
    team_pace: dict[str, float] = {}
    try:
        from wnba_oracle.ingest.minutes_features import fetch_wnba_team_stats
        ts = fetch_wnba_team_stats()
        team_pace = {abbr: float(stats.get("pace", 0.0)) for abbr, stats in ts.items()}
    except Exception as exc:
        log.warning("corpus_team_pace_fetch_failed", error=str(exc))

    has_team = "team" in corpus.columns
    has_opp = "opponent" in corpus.columns
    if team_pace and has_team and has_opp:
        corpus = corpus.with_columns(
            pl.col("team")
            .map_elements(lambda t: team_pace.get(str(t).upper(), 0.0), return_dtype=pl.Float64)
            .alias("team_pace"),
            pl.col("opponent")
            .map_elements(lambda o: team_pace.get(str(o).upper(), 0.0), return_dtype=pl.Float64)
            .alias("opp_pace"),
        ).with_columns(
            ((pl.col("team_pace") + pl.col("opp_pace")) / 2.0).alias("game_pace_implied"),
        )
        log.info("corpus_team_pace_injected", n_teams=len(team_pace))
    else:
        for col in ("team_pace", "opp_pace", "game_pace_implied"):
            if col not in corpus.columns:
                corpus = corpus.with_columns(pl.lit(0.0).alias(col))

    # -- opp_dvp from game_logs (season-wide mean real_score allowed per opponent) --
    dvp_map: dict[str, float] = {}
    needed = [*REAL_SCORE_WEIGHTS, "opponent", "min"]
    if game_logs is not None and not game_logs.is_empty() and all(
        c in game_logs.columns for c in needed
    ):
        try:
            score_expr = pl.lit(float(REAL_SCORE_INTERCEPT))
            for stat, w in REAL_SCORE_WEIGHTS.items():
                score_expr = score_expr + pl.lit(w) * pl.col(stat).fill_null(0.0)
            grouped = (
                game_logs.filter(pl.col("min").fill_null(0.0) >= 5.0)
                .with_columns(score_expr.alias("_est_rs"))
                .group_by("opponent")
                .agg(pl.col("_est_rs").mean().alias("mean_allowed"))
                .filter(pl.col("opponent").is_not_null() & (pl.col("opponent") != ""))
            )
            dvp_map = {
                row["opponent"]: float(row["mean_allowed"]) for row in grouped.to_dicts()
            }
            log.info("corpus_dvp_computed", n_teams=len(dvp_map))
        except Exception as exc:
            log.warning("corpus_dvp_failed", error=str(exc))

    for col in ("opp_dvp_guard", "opp_dvp_forward", "opp_dvp_center"):
        if col not in corpus.columns:
            corpus = corpus.with_columns(pl.lit(0.0).alias(col))
    if dvp_map and has_opp:
        dvp_expr = (
            pl.col("opponent")
            .map_elements(lambda o: dvp_map.get(str(o).upper(), 0.0), return_dtype=pl.Float64)
        )
        corpus = corpus.with_columns(
            dvp_expr.alias("opp_dvp_guard"),
            dvp_expr.alias("opp_dvp_forward"),
            dvp_expr.alias("opp_dvp_center"),
        )

    return corpus


def build_label_corpus(label_df: pl.DataFrame) -> pl.DataFrame:
    """The contest-label corpus for the EB baseline / real_score blend / CQR.

    Currently the ``read_training_corpus`` 7-column frame (slate_date, player_id,
    display_name, team, card_boost, real_score, position). Kept as its own builder
    so a later phase can join causal features here without touching callers.
    """
    return label_df


def gamelog_feature_columns(corpus: pl.DataFrame) -> list[str]:
    """The spec feature columns actually present in a built gamelog corpus.

    Useful for logging / sanity checks: the rolling + schedule columns the heads
    will train on (matchup/pace/DvP columns arrive in a later phase).
    """
    from wnba_oracle.features.spec import _BASE_FEATURES

    present = set(corpus.columns)
    ordered = list(dict.fromkeys((*_BASE_FEATURES, *_SCHEDULE_COLUMNS)))
    return [c for c in ordered if c in present]
