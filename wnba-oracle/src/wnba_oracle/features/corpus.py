"""Assemble the two training corpora (D63, the Phase-1 keystone).

The oracle has two distinct datasets, easy to confuse, used by different
members of the model:

GAMELOG CORPUS -- ``build_gamelog_corpus`` over ~13k ``wnba_game_logs`` rows.
  Grain: one row per player-GAME (stats.wnba.com box score).
  Targets: per-game ``min``, ``real_score`` per-min, etc. (``game_features.add_targets``).
  Features: strictly-causal rolling stats (``game_date < as_of``) +
    schedule + team_pace/opp_dvp enrichment.
  Consumed by: the LightGBM HEADS (minutes + per-minute rate, cohort F).
  This is the dense frame that clears ``low_data_mode`` honestly.

LABEL CORPUS -- ``build_label_corpus`` over ~4.5k ``slate_labels`` rows
  (raw read at ``db.reads.read_label_corpus``).
  Grain: one row per player-SLATE (a Real Sports contest entry).
  Target: realized ``real_score`` on the platform contest.
  Carries: ``card_boost``, ``drafts``, position.
  Consumed by: the EB baseline, the real_score blend, and CQR calibration.

The picker's heads were starved before D63 because training only saw the label
corpus (7 columns with no head target columns); every head was skipped in
``train/pipeline.py``. The gamelog corpus closed that gap.

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
    compute_opp_dvp_map,
    compute_season_game_number,
    compute_team_pace_map,
    to_nba_api_schema,
)
from wnba_oracle.features.rolling import build_rolling_features

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
    causal_dvp: bool = True,
) -> pl.DataFrame:
    """One row per player-game with causal features + per-game targets.

    ``game_logs`` is the stored (lowercase, ISO-date) schema from
    ``db.reads.read_game_logs`` / ``wnba_game_logs.parquet``. A game row is kept
    only if the player has ``>= min_prior_games`` earlier games (so every row
    carries real rolling history); the inner join on the as-of feature frame
    enforces ``>= 1`` and ``min_prior_games`` tightens it further.

    ``causal_dvp=True`` computes each row's ``opp_dvp_*`` from games STRICTLY
    BEFORE that row's ``game_date``, which is what job1 sees at serve time
    (``wnba_game_logs`` only holds already-played games when it runs).
    ``False`` restores the pre-fix season-wide map that included the row's own
    game and later games.
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
    season_game_numbers = compute_season_game_number(game_logs)
    if not season_game_numbers.is_empty():
        corpus = corpus.drop("season_game_number").join(
            season_game_numbers,
            on=["player_id", "season", "game_date"],
            how="left",
        )
    # Position is not carried in game logs; pool into a single cohort ("F") for
    # now. Splitting G/F/C needs a position source (Real Sports pool / identity
    # resolver) and is deferred -- on ~13k rows a single pooled cohort is the
    # small-data-safe choice anyway (research guardrail: do not over-split).
    corpus = corpus.with_columns(pl.lit("F").alias("position"))

    # D77/D108: inject team_pace / opp_pace / game_pace_implied and opp_dvp from
    # the corpus itself. These were zero-filled in earlier builds; populating
    # them here closes the train/serve mismatch introduced by D74.
    # Notes:
    # - team_pace is now point-in-time (computed from games strictly before
    #   each row's date) when causal_pace is True. The legacy nba_api snapshot
    #   behavior remains available for testing via causal_pace=False.
    # - opp_dvp is point-in-time when ``causal_dvp`` is set (games strictly
    #   before each row's date); otherwise the legacy season-wide map.
    corpus = _enrich_corpus_matchup(corpus, game_logs, causal_dvp=causal_dvp, causal_pace=True)

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


def _enrich_corpus_matchup(
    corpus: pl.DataFrame,
    game_logs: pl.DataFrame,
    *,
    causal_dvp: bool = False,
    causal_pace: bool = False,
) -> pl.DataFrame:
    """Add team_pace / opp_pace / game_pace_implied / opp_dvp_* to corpus rows.

    With ``causal_pace=True``, computes team pace from game_logs STRICTLY BEFORE
    each row's game_date (point-in-time, walk-forward safe). When False, uses the
    legacy nba_api current-season snapshot (season-stable, not causal).

    With ``causal_dvp=True``, computes DvP from games strictly before each row's
    date; otherwise uses the season-wide map. Both degrade gracefully to 0 if the
    data source is unavailable.
    """
    has_team = "team" in corpus.columns
    has_opp = "opponent" in corpus.columns

    # -- team pace --
    if causal_pace:
        # Point-in-time pace from game_logs (games strictly before each row's date).
        corpus = _apply_causal_pace(corpus, game_logs) if has_team and has_opp else corpus
    else:
        # Legacy: nba_api current-season snapshot (same as before).
        team_pace: dict[str, float] = {}
        try:
            from wnba_oracle.ingest.minutes_features import fetch_wnba_team_stats

            ts = fetch_wnba_team_stats()
            team_pace = {abbr: float(stats.get("pace", 0.0)) for abbr, stats in ts.items()}
        except Exception as exc:
            log.warning("corpus_team_pace_fetch_failed", error=str(exc))

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

    # -- opp_dvp from game_logs (mean real_score allowed per opponent) --
    for col in ("opp_dvp_guard", "opp_dvp_forward", "opp_dvp_center"):
        if col not in corpus.columns:
            corpus = corpus.with_columns(pl.lit(0.0).alias(col))
    if game_logs is None or game_logs.is_empty() or not has_opp:
        return corpus

    if causal_dvp:
        if "game_date" in corpus.columns and "game_date" in game_logs.columns:
            return _apply_causal_dvp(corpus, game_logs)
        log.warning("corpus_dvp_causal_unavailable", reason="game_date_missing")
        return corpus

    dvp_map: dict[str, float] = {}
    try:
        dvp_map = compute_opp_dvp_map(game_logs)
        log.info("corpus_dvp_computed", n_teams=len(dvp_map))
    except Exception as exc:
        log.warning("corpus_dvp_failed", error=str(exc))
    if dvp_map:
        dvp_expr = pl.col("opponent").map_elements(
            lambda o: dvp_map.get(str(o).upper(), 0.0), return_dtype=pl.Float64
        )
        corpus = corpus.with_columns(
            dvp_expr.alias("opp_dvp_guard"),
            dvp_expr.alias("opp_dvp_forward"),
            dvp_expr.alias("opp_dvp_center"),
        )

    return corpus


def _apply_causal_pace(corpus: pl.DataFrame, game_logs: pl.DataFrame) -> pl.DataFrame:
    """Point-in-time pace: for each corpus date, the per-team pace is built
    from ``game_logs`` rows with ``game_date`` strictly before that date, then
    joined back on ``(game_date, team)`` and ``(game_date, opponent)``. Teams
    with no prior games keep the league mean shrinkage fallback (0.0 if no prior
    games exist at all), matching the serve-time miss value.
    """

    dates = sorted({d for d in corpus.get_column("game_date").to_list() if d})
    lookup_rows: list[dict[str, object]] = []
    n_dates_with_pace = 0
    for d in dates:
        prior = game_logs.filter(pl.col("game_date") < d)
        try:
            pace_map = compute_team_pace_map(prior) if not prior.is_empty() else {}
        except Exception as exc:
            log.warning("corpus_pace_failed", error=str(exc), as_of=d)
            pace_map = {}
        if pace_map:
            n_dates_with_pace += 1
        for team, pace in pace_map.items():
            lookup_rows.append({"game_date": d, "_pace_team": str(team).upper(), "_pace": float(pace)})

    log.info("corpus_pace_computed_causal", n_dates=len(dates), n_dates_with_pace=n_dates_with_pace)
    if not lookup_rows:
        # No prior games across any date: fill with 0.0.
        for col in ("team_pace", "opp_pace", "game_pace_implied"):
            if col not in corpus.columns:
                corpus = corpus.with_columns(pl.lit(0.0).alias(col))
        return corpus

    lookup = pl.from_dicts(
        lookup_rows,
        schema={"game_date": pl.Utf8, "_pace_team": pl.Utf8, "_pace": pl.Float64},
    )

    # Join on team and opponent separately.
    joined = (
        corpus.with_columns(pl.col("team").cast(pl.Utf8).str.to_uppercase().alias("_pace_team"))
        .join(lookup, on=["game_date", "_pace_team"], how="left")
        .with_columns(pl.col("_pace").fill_null(0.0).alias("team_pace"))
        .drop(["_pace_team", "_pace"])
    )

    joined = (
        joined.with_columns(pl.col("opponent").cast(pl.Utf8).str.to_uppercase().alias("_pace_opp"))
        .join(
            lookup.rename({"_pace_team": "_pace_opp"}),
            on=["game_date", "_pace_opp"],
            how="left",
        )
        .with_columns(pl.col("_pace").fill_null(0.0).alias("opp_pace"))
        .drop(["_pace_opp", "_pace"])
    )

    return joined.with_columns(
        ((pl.col("team_pace") + pl.col("opp_pace")) / 2.0).alias("game_pace_implied")
    )


def _apply_causal_dvp(corpus: pl.DataFrame, game_logs: pl.DataFrame) -> pl.DataFrame:
    """Point-in-time DvP: for each corpus date, the per-opponent map is built
    from ``game_logs`` rows with ``game_date`` strictly before that date, then
    joined back on ``(game_date, opponent)``. Rows whose opponent has no prior
    games keep 0.0, matching the serve-time miss value.
    """
    dates = sorted({d for d in corpus.get_column("game_date").to_list() if d})
    lookup_rows: list[dict[str, object]] = []
    n_dates_with_map = 0
    for d in dates:
        prior = game_logs.filter(pl.col("game_date") < d)
        try:
            dvp_map = compute_opp_dvp_map(prior) if not prior.is_empty() else {}
        except Exception as exc:
            log.warning("corpus_dvp_failed", error=str(exc), as_of=d)
            dvp_map = {}
        if dvp_map:
            n_dates_with_map += 1
        for opp, val in dvp_map.items():
            lookup_rows.append({"game_date": d, "_dvp_opp": str(opp).upper(), "_dvp": float(val)})
    log.info("corpus_dvp_computed_causal", n_dates=len(dates), n_dates_with_map=n_dates_with_map)
    if not lookup_rows:
        return corpus
    lookup = pl.from_dicts(
        lookup_rows,
        schema={"game_date": pl.Utf8, "_dvp_opp": pl.Utf8, "_dvp": pl.Float64},
    )
    joined = (
        corpus.with_columns(pl.col("opponent").cast(pl.Utf8).str.to_uppercase().alias("_dvp_opp"))
        .join(lookup, on=["game_date", "_dvp_opp"], how="left")
        .with_columns(pl.col("_dvp").fill_null(0.0))
    )
    return joined.with_columns(
        pl.col("_dvp").alias("opp_dvp_guard"),
        pl.col("_dvp").alias("opp_dvp_forward"),
        pl.col("_dvp").alias("opp_dvp_center"),
    ).drop(["_dvp_opp", "_dvp"])


def build_label_corpus(label_df: pl.DataFrame) -> pl.DataFrame:
    """The contest-label corpus for the EB baseline / real_score blend / CQR.

    Currently the ``read_label_corpus`` 7-column frame (slate_date, player_id,
    display_name, team, card_boost, real_score, position). Kept as its own builder
    so a later phase can join causal features here without touching callers.

    NOTE: this is the per-slate label corpus, NOT the per-game feature corpus.
    The LightGBM heads train on ``build_gamelog_corpus``.
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
