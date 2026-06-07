"""Recent-form / momentum forensics for winning picks.

For every rank-1 (winning) leaderboard lineup across the 141 historical slates,
compute pre-slate rolling real_score over 3/5/10 games for each picked player,
bucket as hot / cold / normal vs that player's season baseline, then compare
that distribution against the universe of available picks on the same slates.
Also test whether Real Sports `card_boost` (pricing) under or over-reacts to
those rolling windows.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
LB_ROOT = REPO / "data" / "historical" / "leaderboards"
CORPUS = REPO / "data" / "processed" / "training_corpus.parquet"
GAMELOG = REPO / "data" / "processed" / "wnba_game_logs.parquet"


def fantasy(row: pd.Series) -> float:
    """Real Sports WNBA fantasy formula used in the training corpus.

    Reverse engineered from corpus per-game real_score: pts + 1.2*reb +
    1.5*ast + 3*stl + 3*blk - tov.  Same as standard FanDuel-style WNBA.
    """
    return (
        row["pts"]
        + 1.2 * row["reb"]
        + 1.5 * row["ast"]
        + 3.0 * row["stl"]
        + 3.0 * row["blk"]
        - row["tov"]
    )


def build_player_map(corpus: pd.DataFrame, gl: pd.DataFrame) -> pd.DataFrame:
    c = corpus[["player_id", "display_name"]].drop_duplicates().copy()
    c["first_initial"] = c["display_name"].str.split(".").str[0].str.strip().str.lower()
    c["last_name"] = c["display_name"].str.split(".").str[1].str.strip().str.lower()
    g = gl[["player_id", "player_name", "first_initial", "last_name"]].drop_duplicates()
    g = g.drop_duplicates(subset=["player_id"])  # unique gl ids
    m = c.merge(g, on=["first_initial", "last_name"], suffixes=("_rs", "_gl"))
    # Dedupe to one rs->gl mapping (first match)
    m = m.drop_duplicates(subset=["player_id_rs"], keep="first")
    return m[["player_id_rs", "display_name", "player_id_gl", "player_name"]]


def load_all_leaderboards() -> pd.DataFrame:
    frames = []
    for d in sorted(LB_ROOT.iterdir()):
        if not d.is_dir():
            continue
        p = d / "data.parquet"
        if not p.exists():
            continue
        frames.append(pd.read_parquet(p))
    return pd.concat(frames, ignore_index=True)


def winners(lb: pd.DataFrame) -> pd.DataFrame:
    """One row per slate per contest with rank=1."""
    w = lb[lb["rank"] == 1].drop_duplicates(subset=["slate_date", "contest_id"], keep="first")
    return w


def expand_lineup(row: pd.Series) -> list[dict]:
    out = []
    for p in json.loads(row["lineup_json"]):
        out.append(
            {
                "slate_date": row["slate_date"],
                "contest_id": row["contest_id"],
                "rank": int(row["rank"]),
                "player_id_rs": int(p["playerId"]),
                "display_name": p["displayName"],
                "multiplier": float(p["multiplier"]),
                "real_score": float(p["value"]),
                "weighted_score": float(p["score"]),
                "injuryStatus": p.get("injuryStatus"),
            }
        )
    return out


def rolling_form(gl: pd.DataFrame, pid_gl: int, slate_date: pd.Timestamp, n: int) -> float | None:
    sub = gl[(gl["player_id"] == pid_gl) & (gl["game_date"] < slate_date)]
    sub = sub.sort_values("game_date").tail(n)
    if len(sub) < min(n, 2):
        return None
    return float(sub["fantasy"].mean())


def baseline_form(gl: pd.DataFrame, pid_gl: int, slate_date: pd.Timestamp) -> float | None:
    sub = gl[(gl["player_id"] == pid_gl) & (gl["game_date"] < slate_date)]
    if len(sub) < 5:
        return None
    return float(sub["fantasy"].mean())


def main() -> None:
    print("loading data...")
    gl = pd.read_parquet(GAMELOG)
    gl["game_date"] = pd.to_datetime(gl["game_date"])
    gl["fantasy"] = gl.apply(fantasy, axis=1)

    corpus = pd.read_parquet(CORPUS)
    corpus["slate_date"] = pd.to_datetime(corpus["slate_date"])

    pmap = build_player_map(corpus, gl)
    rs_to_gl = dict(zip(pmap["player_id_rs"], pmap["player_id_gl"]))
    print(f"player map: {len(rs_to_gl)} rs ids -> gl ids")

    lb = load_all_leaderboards()
    lb["slate_date"] = pd.to_datetime(lb["slate_date"])
    print(f"leaderboards: {len(lb)} rows across {lb['slate_date'].nunique()} slates")

    w = winners(lb)
    print(f"winners (1 per slate*contest): {len(w)}")

    # Expand all winning picks
    rows = []
    for _, r in w.iterrows():
        rows.extend(expand_lineup(r))
    winpicks = pd.DataFrame(rows)
    winpicks["player_id_gl"] = winpicks["player_id_rs"].map(rs_to_gl)
    n_unmapped = winpicks["player_id_gl"].isna().sum()
    print(f"winning picks: {len(winpicks)}, unmapped to gl: {n_unmapped}")

    # Compute rolling form windows
    for n in (3, 5, 10):
        winpicks[f"r{n}"] = [
            rolling_form(gl, int(g), d, n) if pd.notna(g) else None
            for g, d in zip(winpicks["player_id_gl"], winpicks["slate_date"])
        ]
    winpicks["base"] = [
        baseline_form(gl, int(g), d) if pd.notna(g) else None
        for g, d in zip(winpicks["player_id_gl"], winpicks["slate_date"])
    ]

    # Bucket: hot if r3 - base >= +3; cold if <= -3; normal otherwise
    def bucket(r: float | None, base: float | None) -> str:
        if r is None or base is None or pd.isna(r) or pd.isna(base):
            return "unknown"
        delta = r - base
        if delta >= 3.0:
            return "hot"
        if delta <= -3.0:
            return "cold"
        return "normal"

    winpicks["bucket_r3"] = [bucket(r, b) for r, b in zip(winpicks["r3"], winpicks["base"])]
    winpicks["bucket_r5"] = [bucket(r, b) for r, b in zip(winpicks["r5"], winpicks["base"])]
    winpicks["bucket_r10"] = [bucket(r, b) for r, b in zip(winpicks["r10"], winpicks["base"])]
    winpicks["delta_r3"] = winpicks["r3"] - winpicks["base"]
    winpicks["delta_r5"] = winpicks["r5"] - winpicks["base"]

    # Available picks baseline: every (slate, player) in corpus
    corpus["player_id_gl"] = corpus["player_id"].map(rs_to_gl)
    for n in (3, 5, 10):
        corpus[f"r{n}"] = [
            rolling_form(gl, int(g), d, n) if pd.notna(g) else None
            for g, d in zip(corpus["player_id_gl"], corpus["slate_date"])
        ]
    corpus["base"] = [
        baseline_form(gl, int(g), d) if pd.notna(g) else None
        for g, d in zip(corpus["player_id_gl"], corpus["slate_date"])
    ]
    corpus["bucket_r3"] = [bucket(r, b) for r, b in zip(corpus["r3"], corpus["base"])]
    corpus["bucket_r5"] = [bucket(r, b) for r, b in zip(corpus["r5"], corpus["base"])]
    corpus["delta_r3"] = corpus["r3"] - corpus["base"]
    corpus["delta_r5"] = corpus["r5"] - corpus["base"]

    # Save intermediates
    out = REPO / "research" / "players_environment" / "_form_winpicks.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    winpicks.to_parquet(out)
    corpus.to_parquet(REPO / "research" / "players_environment" / "_form_corpus.parquet")

    # ---- Summary stats ----
    print("\n=== WINNING PICK form bucket distribution (r3) ===")
    print(winpicks["bucket_r3"].value_counts(normalize=True))
    print("\n=== CORPUS available pick distribution (r3) ===")
    print(corpus["bucket_r3"].value_counts(normalize=True))

    print("\n=== WINNING PICK form bucket distribution (r5) ===")
    print(winpicks["bucket_r5"].value_counts(normalize=True))
    print("\n=== CORPUS available pick distribution (r5) ===")
    print(corpus["bucket_r5"].value_counts(normalize=True))

    print("\n=== MEAN delta r3 (recent - season) ===")
    print("winning picks:", winpicks["delta_r3"].mean(), "n=", winpicks["delta_r3"].notna().sum())
    print("available    :", corpus["delta_r3"].mean(), "n=", corpus["delta_r3"].notna().sum())

    # Correlation of card_boost with rolling form. Boost is the Real Sports pricing
    # multiplier (higher boost = cheaper / better deal). Negative corr with form
    # = pricing reacts to recent form (hot players priced down / lower boost?
    # actually higher boost is the bonus -- means RS gives MORE bonus to lower
    # performers). Let's just look at boost vs r5 and vs base.
    merged = corpus.dropna(subset=["base", "r5"]).copy()
    merged["delta_r5_vs_base"] = merged["r5"] - merged["base"]
    print("\n=== Real Sports pricing reaction ===")
    print("corr(card_boost, season_base) =", merged[["card_boost", "base"]].corr().iloc[0, 1])
    print("corr(card_boost, r5)         =", merged[["card_boost", "r5"]].corr().iloc[0, 1])
    print("corr(card_boost, delta_r5)   =", merged[["card_boost", "delta_r5_vs_base"]].corr().iloc[0, 1])

    # Real result correlation: how well does each window predict slate real_score?
    # The corpus already has the realized real_score per (slate, player).
    pred = merged.dropna(subset=["real_score"]).copy()
    print("\n=== Predictive power of recent form (corr with realized real_score) ===")
    for col in ["base", "r3", "r5", "r10", "delta_r5_vs_base"]:
        if col in pred.columns:
            sub = pred.dropna(subset=[col])
            print(f"  {col:20s}  corr={sub[[col,'real_score']].corr().iloc[0,1]:.4f}  n={len(sub)}")

    # Win-rate uplift: among hot picks vs cold picks in corpus, who actually
    # produced the highest slate real_score?
    print("\n=== Realized real_score by bucket (corpus) ===")
    print(corpus.groupby("bucket_r5")["real_score"].agg(["mean", "median", "count"]))
    print("\n=== Realized real_score by bucket (winning picks only) ===")
    print(winpicks.groupby("bucket_r5")["real_score"].agg(["mean", "median", "count"]))

    # Per-multiplier tier breakdown - what bucket are the 2x slots?
    winpicks["mult_band"] = winpicks["multiplier"].round(1)
    print("\n=== Winning-pick bucket by multiplier tier (r5) ===")
    ct = pd.crosstab(winpicks["mult_band"], winpicks["bucket_r5"], normalize="index")
    print(ct)

    # Top winning pick players and their typical pre-slate form
    print("\n=== Most-frequent winning-pick players + typical pre-slate r5 delta ===")
    by_player = (
        winpicks.dropna(subset=["delta_r5"])
        .groupby("display_name")
        .agg(picks=("display_name", "size"), mean_delta_r5=("delta_r5", "mean"), mean_r5=("r5", "mean"))
        .sort_values("picks", ascending=False)
        .head(25)
    )
    print(by_player)

    # Save final tables for the markdown writer
    out_dir = REPO / "research" / "players_environment"
    by_player.to_csv(out_dir / "_form_by_player.csv")

    print("\nDone. winpicks -> _form_winpicks.parquet; corpus -> _form_corpus.parquet")


if __name__ == "__main__":
    main()
