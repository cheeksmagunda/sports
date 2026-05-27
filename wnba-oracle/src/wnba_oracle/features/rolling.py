"""Rolling-window features computed strictly before slate_date.

Input: Polars DataFrame of per-player game logs (one row per game).
Output: per-player rolling aggregates for windows L5, L10, L20.

The rolling computation MUST be left-closed strict: features at
slate_date are computed from games with `game_date < slate_date`. Including
the slate_date game itself would be post-game leakage.

WNBA fantasy points (Real Sports approximation used for fantasy_pts_l5/10):
    pts + 1.2 * reb + 1.5 * ast + 3 * stl + 3 * blk - 1 * tov

This formula is a documented proxy because Real Sports' true Real Score
formula is not exposed. It only enters as a rolling baseline feature, not
as a label. The LightGBM heads learn against the platform's actual
real_score from contest_stats.
"""

from __future__ import annotations

import polars as pl


def fantasy_pts_expr() -> pl.Expr:
    return (
        pl.col("PTS").cast(pl.Float64)
        + 1.2 * pl.col("REB").cast(pl.Float64)
        + 1.5 * pl.col("AST").cast(pl.Float64)
        + 3.0 * pl.col("STL").cast(pl.Float64)
        + 3.0 * pl.col("BLK").cast(pl.Float64)
        - 1.0 * pl.col("TOV").cast(pl.Float64)
    )


def add_per_game_rates(df: pl.DataFrame) -> pl.DataFrame:
    """Per-minute / per-game derived columns used by the rolling windows."""
    return df.with_columns(
        [
            fantasy_pts_expr().alias("FANTASY_PTS"),
            (
                pl.when(pl.col("MIN") > 0)
                .then(pl.col("PTS").cast(pl.Float64) / pl.col("MIN").cast(pl.Float64))
                .otherwise(0.0)
            ).alias("PTS_PER_MIN"),
            (
                pl.when(pl.col("MIN") > 0)
                .then(pl.col("REB").cast(pl.Float64) / pl.col("MIN").cast(pl.Float64))
                .otherwise(0.0)
            ).alias("REB_PER_MIN"),
            (
                pl.when(pl.col("MIN") > 0)
                .then(pl.col("AST").cast(pl.Float64) / pl.col("MIN").cast(pl.Float64))
                .otherwise(0.0)
            ).alias("AST_PER_MIN"),
            (
                pl.when(pl.col("MIN") > 0)
                .then(
                    (pl.col("STL").cast(pl.Float64) + pl.col("BLK").cast(pl.Float64))
                    / pl.col("MIN").cast(pl.Float64)
                )
                .otherwise(0.0)
            ).alias("STL_BLK_PER_MIN"),
            (
                pl.when(pl.col("TOV") > 0)
                .then(pl.col("AST").cast(pl.Float64) / pl.col("TOV").cast(pl.Float64))
                .otherwise(pl.col("AST").cast(pl.Float64))
            ).alias("AST_TO_TOV"),
        ]
    )


def build_rolling_features(
    game_log: pl.DataFrame,
    *,
    as_of_date: str,
    windows: tuple[int, ...] = (5, 10, 20),
) -> pl.DataFrame:
    """One row per Player_ID, with rolling-window aggregates over games
    strictly before `as_of_date` (ISO YYYY-MM-DD).

    Returns columns:
        player_id, mins_l5, mins_l10, mins_l20,
        pts_l5, pts_l10, reb_l5, reb_l10, ast_l5, ast_l10,
        stl_l5, stl_l10, blk_l5, blk_l10, tov_l5, tov_l10,
        fg3m_l5, fg3m_l10,
        fantasy_pts_l5, fantasy_pts_l10,
        pts_per_min_l5, pts_per_min_l10,
        reb_per_min_l10, ast_per_min_l10, stl_blk_per_min_l10,
        ts_pct_l10, efg_pct_l10, usg_pct_l10, ast_to_tov_l10,
        fg3_pct_l10, plus_minus_l10, foul_rate_l10,
        coach_rotation_consistency_l20
    """
    if game_log.is_empty():
        return _empty_rolling(windows)

    df = add_per_game_rates(game_log)
    # Parse GAME_DATE as a real Date for ordering. nba_api returns it as
    # "MMM DD, YYYY" by default (e.g., "MAY 18, 2026"). Try several formats.
    df = df.with_columns(
        pl.coalesce(
            pl.col("GAME_DATE").str.to_date("%b %d, %Y", strict=False),
            pl.col("GAME_DATE").str.to_date("%Y-%m-%d", strict=False),
            pl.col("GAME_DATE").str.to_date("%Y/%m/%d", strict=False),
        ).alias("_game_date")
    )
    as_of = pl.lit(as_of_date).str.to_date("%Y-%m-%d", strict=True)
    df = df.filter(pl.col("_game_date") < as_of)

    # Sort within each player so head(n) is the most-recent n games.
    df = df.sort(["Player_ID", "_game_date"], descending=[False, True])

    rows: list[dict[str, float | int]] = []
    for (pid,), grp in df.group_by(["Player_ID"]):
        rec: dict[str, float | int] = {"player_id": int(pid)}
        for w in windows:
            window_df = grp.head(w)
            if window_df.is_empty():
                _fill_zero(rec, w)
                continue
            stats = window_df.select(
                [
                    pl.col("MIN").cast(pl.Float64).mean().alias(f"mins_l{w}"),
                    pl.col("PTS").cast(pl.Float64).mean().alias(f"pts_l{w}"),
                    pl.col("REB").cast(pl.Float64).mean().alias(f"reb_l{w}"),
                    pl.col("AST").cast(pl.Float64).mean().alias(f"ast_l{w}"),
                    pl.col("STL").cast(pl.Float64).mean().alias(f"stl_l{w}"),
                    pl.col("BLK").cast(pl.Float64).mean().alias(f"blk_l{w}"),
                    pl.col("TOV").cast(pl.Float64).mean().alias(f"tov_l{w}"),
                    pl.col("FG3M").cast(pl.Float64).mean().alias(f"fg3m_l{w}"),
                    pl.col("FANTASY_PTS").mean().alias(f"fantasy_pts_l{w}"),
                    pl.col("PTS_PER_MIN").mean().alias(f"pts_per_min_l{w}"),
                ]
            ).to_dicts()[0]
            rec.update({k: float(v) for k, v in stats.items() if v is not None})
        # L10-only metrics
        l10 = grp.head(10)
        if not l10.is_empty():
            l10_stats = l10.select(
                [
                    pl.col("REB_PER_MIN").mean().alias("reb_per_min_l10"),
                    pl.col("AST_PER_MIN").mean().alias("ast_per_min_l10"),
                    pl.col("STL_BLK_PER_MIN").mean().alias("stl_blk_per_min_l10"),
                    pl.col("AST_TO_TOV").mean().alias("ast_to_tov_l10"),
                    pl.col("PLUS_MINUS").cast(pl.Float64).mean().alias("plus_minus_l10")
                    if "PLUS_MINUS" in l10.columns
                    else pl.lit(0.0).alias("plus_minus_l10"),
                ]
            ).to_dicts()[0]
            rec.update({k: float(v) for k, v in l10_stats.items() if v is not None})
            # Derived shooting percentages
            tot = l10.select(
                [
                    pl.col("PTS").cast(pl.Float64).sum().alias("p_sum"),
                    pl.col("FGA").cast(pl.Float64).sum().alias("fga_sum")
                    if "FGA" in l10.columns
                    else pl.lit(0.0).alias("fga_sum"),
                    pl.col("FTA").cast(pl.Float64).sum().alias("fta_sum")
                    if "FTA" in l10.columns
                    else pl.lit(0.0).alias("fta_sum"),
                    pl.col("FG3M").cast(pl.Float64).sum().alias("fg3m_sum"),
                    pl.col("FG3A").cast(pl.Float64).sum().alias("fg3a_sum")
                    if "FG3A" in l10.columns
                    else pl.lit(0.0).alias("fg3a_sum"),
                ]
            ).to_dicts()[0]
            true_shooting_denom = 2.0 * (
                float(tot["fga_sum"]) + 0.44 * float(tot["fta_sum"])
            )
            rec["ts_pct_l10"] = (
                float(tot["p_sum"]) / true_shooting_denom if true_shooting_denom > 0 else 0.0
            )
            rec["efg_pct_l10"] = (
                (float(tot["p_sum"]) - float(tot["fta_sum"]))  # rough proxy
                / (2.0 * float(tot["fga_sum"]))
                if tot["fga_sum"] > 0
                else 0.0
            )
            rec["fg3_pct_l10"] = (
                float(tot["fg3m_sum"]) / float(tot["fg3a_sum"])
                if tot["fg3a_sum"] > 0
                else 0.0
            )
            # USG% proxy: (FGA + 0.44*FTA + TOV) per 36 min relative to team
            # is the canonical formula. Without team context per game, fall
            # back to per-min usage (still informative as a player-level rate).
            min_sum = (
                l10.select(pl.col("MIN").cast(pl.Float64).sum()).to_dicts()[0]["MIN"]
                if "MIN" in l10.columns
                else 0.0
            )
            tov_sum = (
                l10.select(pl.col("TOV").cast(pl.Float64).sum()).to_dicts()[0]["TOV"]
                if "TOV" in l10.columns
                else 0.0
            )
            usage_num = float(tot["fga_sum"]) + 0.44 * float(tot["fta_sum"]) + float(tov_sum)
            rec["usg_pct_l10"] = usage_num / float(min_sum) if min_sum > 0 else 0.0
            # Foul rate (PF column in nba_api) and rotation consistency
            pf_sum = (
                float(
                    l10.select(pl.col("PF").cast(pl.Float64).sum()).to_dicts()[0]["PF"]
                )
                if "PF" in l10.columns
                else 0.0
            )
            rec["foul_rate_l10"] = pf_sum / float(min_sum) if min_sum > 0 else 0.0
        l20 = grp.head(20)
        if not l20.is_empty() and "MIN" in l20.columns:
            mins_arr = l20.select(pl.col("MIN").cast(pl.Float64)).to_series().to_list()
            if len(mins_arr) > 1:
                mean = sum(mins_arr) / len(mins_arr)
                var = sum((m - mean) ** 2 for m in mins_arr) / (len(mins_arr) - 1)
                rec["coach_rotation_consistency_l20"] = float(var) ** 0.5
            else:
                rec["coach_rotation_consistency_l20"] = 0.0
        else:
            rec["coach_rotation_consistency_l20"] = 0.0
        rows.append(rec)
    return pl.from_dicts(rows) if rows else _empty_rolling(windows)


def _fill_zero(rec: dict[str, float | int], w: int) -> None:
    for stat in (
        "mins",
        "pts",
        "reb",
        "ast",
        "stl",
        "blk",
        "tov",
        "fg3m",
        "fantasy_pts",
        "pts_per_min",
    ):
        rec[f"{stat}_l{w}"] = 0.0


def _empty_rolling(windows: tuple[int, ...]) -> pl.DataFrame:
    cols: dict[str, list[float]] = {"player_id": []}
    base_stats = (
        "mins",
        "pts",
        "reb",
        "ast",
        "stl",
        "blk",
        "tov",
        "fg3m",
        "fantasy_pts",
        "pts_per_min",
    )
    for w in windows:
        for s in base_stats:
            cols[f"{s}_l{w}"] = []
    extra = (
        "reb_per_min_l10",
        "ast_per_min_l10",
        "stl_blk_per_min_l10",
        "ast_to_tov_l10",
        "plus_minus_l10",
        "ts_pct_l10",
        "efg_pct_l10",
        "fg3_pct_l10",
        "usg_pct_l10",
        "foul_rate_l10",
        "coach_rotation_consistency_l20",
    )
    for c in extra:
        cols[c] = []
    return pl.DataFrame(cols)
