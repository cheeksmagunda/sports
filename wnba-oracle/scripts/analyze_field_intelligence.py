"""Field-intelligence study for issue #37 (community lineup intelligence).

Read-only, rerunnable analysis of the contest-native corpus that answers
issue #37 sections A-C and the 2026-08-30 audit-comment questions (winner vs
theoretical ceiling). Nothing here writes to any table or changes picker
behavior.

Inputs are files, never a database connection:

  --labels-csv        slate_labels export (``scripts/backup_corpus.py`` writes
                      ``data/backups/slate_labels.csv``; the ``backups`` branch
                      carries the daily snapshot).
  --leaderboards-csv  optional contest_leaderboards export from the same
                      snapshot. ``user_id`` is replaced by a truncated sha256
                      at load time and is never printed; only aggregates are
                      reported.
  --dossier-dir       optional cache of ``GET /dossier/{date}`` JSON files
                      named ``YYYY-MM-DD.json`` (public read-only API).
  --lineup-dir        optional cache of ``GET /lineup/{date}`` JSON files.

Sections:
  A. audit_labels / audit_leaderboards / dossier coverage: completeness and
     censoring of the corpus.
  B. popularity_value_correlation / ceiling_popularity_membership /
     leaderboard profiling (ownership skew by rank, slot/boost ordering,
     repeat finishers, top-20 duplication).
  C. serving_knob_history + dossier_gap_summary: what the objective actually
     ran with, and how far winners sit from the realized ceiling.

Run from the monorepo root:
  uv run --frozen --package wnba-oracle python \
      wnba-oracle/scripts/analyze_field_intelligence.py \
      --labels-csv wnba-oracle/data/backups/slate_labels.csv \
      --leaderboards-csv wnba-oracle/data/backups/contest_leaderboards.csv \
      --dossier-dir <cache> --lineup-dir <cache> --json-out <path>
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import pathlib
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

SLOT_BASES: tuple[float, ...] = (2.0, 1.8, 1.6, 1.4, 1.2)
DEFAULT_SINCE = "2026-05-27"  # contest_leaderboards live-capture start (issue #37)
CEILING_PRUNE = 26  # matches dossier._realized_oracle
LABEL_COMPLETE_MIN_ROWS = 37  # matches dossier ceiling censoring threshold
REQUIRED_LABEL_COLUMNS = frozenset(
    {
        "slate_date",
        "section",
        "platform_player_id",
        "team_key",
        "card_boost",
        "drafts",
        "real_score",
    }
)
REQUIRED_LEADERBOARD_COLUMNS = frozenset({"slate_date", "rank", "user_id", "score", "lineup"})
# Keys as job2 writes them into frozen_lineups.lineup["serving_knobs"].
SERVING_KNOBS = (
    "leverage_weight",
    "duplication_weight",
    "ceiling_weight",
    "committed_order_objective",
    "duplication_aware_payout",
    "ceiling_tilt_slots",
    "field_measured_ownership_enabled",
)


# ---------------------------------------------------------------------------
# Loading (the only I/O besides main's printing)
# ---------------------------------------------------------------------------


def pseudonymize(user_id: object) -> str:
    """Stable, non-reversible-in-practice token for a platform user slug."""
    return hashlib.sha256(str(user_id).encode("utf-8")).hexdigest()[:12]


def load_labels(path: pathlib.Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"slate_date": str})
    missing = REQUIRED_LABEL_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"slate_labels export missing columns: {sorted(missing)}")
    return df


def load_leaderboards(path: pathlib.Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"slate_date": str, "user_id": str})
    missing = REQUIRED_LEADERBOARD_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"contest_leaderboards export missing columns: {sorted(missing)}")
    df["user_token"] = df["user_id"].map(pseudonymize)
    return df.drop(columns=["user_id"])


def load_json_dir(directory: pathlib.Path) -> dict[str, dict[str, Any]]:
    """Load ``YYYY-MM-DD.json`` API responses; skip 404 bodies and bad JSON."""
    out: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.glob("*.json")):
        try:
            body = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(body, dict) and "detail" not in body:
            out[path.stem] = body
    return out


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def spearman(x: Sequence[float], y: Sequence[float]) -> float:
    xs = pd.Series(list(x), dtype=float)
    ys = pd.Series(list(y), dtype=float)
    mask = xs.notna() & ys.notna()
    if mask.sum() < 3 or xs[mask].nunique() < 2 or ys[mask].nunique() < 2:
        return float("nan")
    return float(xs[mask].rank().corr(ys[mask].rank()))


def bootstrap_ci(
    values: Sequence[float], *, n_boot: int = 2000, seed: int = 37, q: float = 0.95
) -> tuple[float, float, float]:
    """Mean and percentile CI over a slate-level statistic (slates resampled)."""
    arr = np.asarray([v for v in values if not math.isnan(v)], dtype=float)
    if arr.size == 0:
        return (float("nan"), float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    boots = rng.choice(arr, size=(n_boot, arr.size), replace=True).mean(axis=1)
    lo, hi = np.quantile(boots, [(1 - q) / 2, 1 - (1 - q) / 2])
    return (float(arr.mean()), float(lo), float(hi))


def boosted_value(real_score: float, card_boost: float, slot_base: float = 2.0) -> float:
    """Top-slot contribution, the unit the platform's own sections rank by."""
    return float(real_score) * (slot_base + float(card_boost))


def effective_team_cap(n_teams: int, max_per_team: int = 2) -> int:
    """Mirror Settings.optimizer_dynamic_team_cap (D50) from a team count."""
    games = max(1, n_teams // 2)
    if games <= 1:
        return 5
    if games == 2:
        return max(max_per_team, 3)
    return max_per_team


def parse_lineup(raw: object) -> list[dict[str, float]]:
    """Parse one contest_leaderboards.lineup value into committed-order picks.

    ``multiplier`` on the platform is slot_base + multiplierBonus, so the
    slot base is recovered as their difference. Raises ValueError on a
    lineup that does not have exactly five parseable picks.
    """
    picks = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(picks, list) or len(picks) != 5:
        raise ValueError("lineup must be a list of exactly 5 picks")
    out = []
    for i, p in enumerate(picks):
        mult = float(p["multiplier"])
        bonus = float(p.get("multiplierBonus") or 0.0)
        out.append(
            {
                "order": float(p.get("order", i)),
                "player_id": float(p["playerId"]),
                "value": float(p["value"]),
                "boost": bonus,
                "slot_base": round(mult - bonus, 4),
            }
        )
    out.sort(key=lambda r: r["order"])
    return out


def realized_ceiling(pool: pd.DataFrame, cap: int) -> tuple[float, list[int]]:
    """Best 5-player realized lineup under a per-team cap (hindsight order).

    Same pruning as dossier._realized_oracle, so the score is a lower bound
    on the true ceiling of the *observed* pool, which is itself only the
    players the platform's community sections surfaced.
    """
    rows = pool.dropna(subset=["real_score"]).copy()
    rows["_ub"] = rows["real_score"].astype(float) * (2.0 + rows["card_boost"].astype(float))
    rows = rows.sort_values("_ub", ascending=False).head(CEILING_PRUNE)
    if len(rows) < 5:
        return (float("nan"), [])
    vals = rows["real_score"].to_numpy(float)
    boosts = rows["card_boost"].to_numpy(float)
    teams = rows["team_key"].astype(str).to_numpy()
    pids = rows["platform_player_id"].astype(int).to_numpy()
    slots = np.array(SLOT_BASES)
    best, best_idx = -math.inf, None
    for combo in itertools.combinations(range(len(rows)), 5):
        idx = list(combo)
        if cap < 5 and max(Counter(teams[idx]).values()) > cap:
            continue
        v, b = vals[idx], boosts[idx]
        o = np.argsort(v)[::-1]
        s = float(np.sum(v[o] * (slots + b[o])))
        if s > best:
            best, best_idx = s, idx
    if best_idx is None:
        return (float("nan"), [])
    return (best, [int(pids[i]) for i in best_idx])


def dedupe_pool(labels: pd.DataFrame) -> pd.DataFrame:
    """One row per (slate, player); a player can appear in several sections."""
    return (
        labels.sort_values(["slate_date", "platform_player_id", "drafts"], na_position="first")
        .drop_duplicates(["slate_date", "platform_player_id"], keep="last")
        .reset_index(drop=True)
    )


# ---------------------------------------------------------------------------
# Section A: audit
# ---------------------------------------------------------------------------


def audit_labels(labels: pd.DataFrame, since: str = DEFAULT_SINCE) -> dict[str, Any]:
    window = labels[labels["slate_date"] >= since]
    per_slate = window.groupby("slate_date").size()
    slates = sorted(window["slate_date"].unique())
    gaps = []
    for a, b in itertools.pairwise(slates):
        delta = (pd.Timestamp(b) - pd.Timestamp(a)).days
        if delta > 3:
            gaps.append({"after": a, "before": b, "days": int(delta)})
    return {
        "all_rows": len(labels),
        "all_slates": int(labels["slate_date"].nunique()),
        "min_slate": str(labels["slate_date"].min()),
        "max_slate": str(labels["slate_date"].max()),
        "window_since": since,
        "window_slates": len(slates),
        "window_rows": len(window),
        "rows_per_slate_median": float(per_slate.median()) if len(per_slate) else float("nan"),
        "rows_per_slate_min": int(per_slate.min()) if len(per_slate) else 0,
        "slates_below_ceiling_threshold": int((per_slate < LABEL_COMPLETE_MIN_ROWS).sum()),
        "section_counts": {str(k): int(v) for k, v in window["section"].value_counts().items()},
        "null_drafts_share": float(window["drafts"].isna().mean()) if len(window) else 0.0,
        "null_real_score_rows": int(window["real_score"].isna().sum()),
        "duplicate_player_rows": int(window.duplicated(["slate_date", "platform_player_id"]).sum()),
        "calendar_gaps_over_3_days": gaps,
    }


def audit_leaderboards(lb: pd.DataFrame, since: str = DEFAULT_SINCE) -> dict[str, Any]:
    window = lb[lb["slate_date"] >= since]
    per_slate = window.groupby("slate_date").size()
    bad = 0
    for raw in window["lineup"]:
        try:
            parse_lineup(raw)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            bad += 1
    has_rank1 = window.groupby("slate_date")["rank"].min().eq(1)
    return {
        "window_slates": int(window["slate_date"].nunique()),
        "window_rows": len(window),
        "rows_per_slate_counts": {int(k): int(v) for k, v in per_slate.value_counts().items()},
        "slates_missing_rank1": int((~has_rank1).sum()),
        "unparseable_lineups": bad,
        "distinct_users": int(window["user_token"].nunique()),
    }


def dossier_coverage(
    dossiers: Mapping[str, Mapping[str, Any]], label_slates: Iterable[str]
) -> dict[str, Any]:
    label_set = set(label_slates)
    have = set(dossiers)
    return {
        "dossiers": len(have),
        "label_slates_without_dossier": sorted(label_set - have),
        "dossiers_without_labels": sorted(have - label_set),
    }


# ---------------------------------------------------------------------------
# Section B: field behavior from community sections
# ---------------------------------------------------------------------------


def popularity_value_correlation(labels: pd.DataFrame) -> dict[str, Any]:
    """Direct check on popularity.py's ported -0.457 claim.

    Reported per section because each platform section is selected on a
    different variable (``highestBoostedValuePlayers`` on the outcome,
    ``popularPlayers`` on drafts), so a pooled correlation mixes two
    selection biases. The slate-level mean (with a slate-bootstrap CI) is
    the headline; the pooled value is shown only for comparison.
    """
    df = labels.dropna(subset=["drafts", "real_score"]).copy()
    df["boosted_value"] = df["real_score"] * (2.0 + df["card_boost"])
    out: dict[str, Any] = {}
    groups: dict[str, pd.DataFrame] = {"all_sections_dedup": dedupe_pool(df)}
    for section, sub in df.groupby("section"):
        groups[str(section)] = sub
    for name, sub in groups.items():
        per_slate_boost, per_slate_bv, per_slate_rs = [], [], []
        for _, s in sub.groupby("slate_date"):
            if len(s) < 5:
                continue
            per_slate_boost.append(spearman(s["drafts"], s["card_boost"]))
            per_slate_bv.append(spearman(s["drafts"], s["boosted_value"]))
            per_slate_rs.append(spearman(s["drafts"], s["real_score"]))
        out[name] = {
            "n_rows": len(sub),
            "n_slates": len(per_slate_bv),
            "drafts_vs_card_boost": bootstrap_ci(per_slate_boost),
            "drafts_vs_boosted_value": bootstrap_ci(per_slate_bv),
            "drafts_vs_real_score": bootstrap_ci(per_slate_rs),
            "pooled_drafts_vs_boosted_value": spearman(sub["drafts"], sub["boosted_value"]),
        }
    return out


def half_split_value_ratio(labels: pd.DataFrame) -> tuple[float, float, float]:
    """Per slate: total boosted value of the least-drafted half / most-drafted half.

    basketball-main reported ~1.24-1.26 for NBA. Returns slate-bootstrap
    (mean, lo, hi) of the per-slate ratio on the deduplicated observed pool.
    """
    df = dedupe_pool(labels.dropna(subset=["drafts", "real_score"]))
    ratios = []
    for _, s in df.groupby("slate_date"):
        if len(s) < 6:
            continue
        s = s.sort_values("drafts")
        half = len(s) // 2
        low = (s.head(half)["real_score"] * (2.0 + s.head(half)["card_boost"])).sum()
        high = (s.tail(half)["real_score"] * (2.0 + s.tail(half)["card_boost"])).sum()
        if high > 0:
            ratios.append(float(low / high))
    return bootstrap_ci(ratios)


def ceiling_popularity_membership(labels: pd.DataFrame) -> dict[str, Any]:
    """Where do the realized-ceiling lineup's players sit in the drafts ranking?

    Answers the audit comment's fifth question in its unconditional form:
    does popularity predict membership in the hindsight-ceiling lineup?
    ``drafts_pct`` is the within-slate percentile of drafts (1.0 = most
    drafted). Under no relationship the mean is ~0.5.
    """
    pool = dedupe_pool(labels.dropna(subset=["real_score"]))
    per_slate = []
    for sd, s in pool.groupby("slate_date"):
        if len(s) < 5 or s["drafts"].notna().sum() < 5:
            continue
        cap = effective_team_cap(s["team_key"].nunique())
        score, pids = realized_ceiling(s, cap)
        if not pids:
            continue
        pct = s["drafts"].rank(pct=True)
        members = s["platform_player_id"].astype(int).isin(pids)
        member_pct = pct[members].dropna()
        per_slate.append(
            {
                "slate_date": sd,
                "ceiling": score,
                "cap": cap,
                "member_drafts_pct_mean": float(member_pct.mean()),
                "members_top_quartile_drafts": int((member_pct > 0.75).sum()),
                "members_bottom_half_drafts": int((member_pct <= 0.5).sum()),
                "member_boost_mean": float(s.loc[members, "card_boost"].mean()),
                "pool_boost_mean": float(s["card_boost"].mean()),
            }
        )
    frame = pd.DataFrame(per_slate)
    if frame.empty:
        return {"n_slates": 0}
    return {
        "n_slates": len(frame),
        "member_drafts_pct_mean": bootstrap_ci(frame["member_drafts_pct_mean"].tolist()),
        "members_top_quartile_per_lineup": float(frame["members_top_quartile_drafts"].mean()),
        "members_bottom_half_per_lineup": float(frame["members_bottom_half_drafts"].mean()),
        "member_boost_mean": float(frame["member_boost_mean"].mean()),
        "pool_boost_mean": float(frame["pool_boost_mean"].mean()),
        "per_slate": frame,
    }


# ---------------------------------------------------------------------------
# Section B: leaderboard profiling (needs contest_leaderboards)
# ---------------------------------------------------------------------------


def explode_leaderboards(lb: pd.DataFrame) -> pd.DataFrame:
    """One row per (entry, pick) with slot index, slot base, boost, value."""
    rows = []
    for rec in lb.itertuples(index=False):
        try:
            picks = parse_lineup(rec.lineup)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            continue
        for slot_idx, p in enumerate(picks):
            rows.append(
                {
                    "slate_date": rec.slate_date,
                    "rank": int(rec.rank),
                    "user_token": getattr(rec, "user_token", ""),
                    "score": float(rec.score),
                    "slot_idx": slot_idx,
                    "player_id": int(p["player_id"]),
                    "value": p["value"],
                    "boost": p["boost"],
                    "slot_base": p["slot_base"],
                }
            )
    return pd.DataFrame(rows)


def slot_order_profile(lb: pd.DataFrame) -> dict[str, Any]:
    """How close top-20 committed slot orders are to hindsight-optimal.

    ``headroom`` = hindsight_max - committed for the same five players.
    ``top_slot_is_max_value`` = the player in the 2.0x slot had the highest
    realized value in the lineup (what p50/rearrangement ordering targets
    when the prediction is right).
    """
    headroom, top_is_max, top_is_min_boost, spearman_boost_slot = [], [], [], []
    for raw in lb["lineup"]:
        try:
            picks = parse_lineup(raw)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            continue
        values = [p["value"] for p in picks]
        boosts = [p["boost"] for p in picks]
        bases = [p["slot_base"] for p in picks]
        committed = sum(v * (sb + b) for v, b, sb in zip(values, boosts, bases, strict=True))
        order = sorted(range(5), key=lambda i: values[i], reverse=True)
        hind = sum(
            values[i] * (base + boosts[i])
            for i, base in zip(order, sorted(bases, reverse=True), strict=True)
        )
        headroom.append(hind - committed)
        top = int(np.argmax(bases))
        top_is_max.append(float(values[top] == max(values)))
        top_is_min_boost.append(float(boosts[top] == min(boosts)))
        spearman_boost_slot.append(spearman(bases, boosts))
    return {
        "n_entries": len(headroom),
        "headroom": bootstrap_ci(headroom),
        "share_zero_headroom": float(np.mean([h < 1e-6 for h in headroom])) if headroom else 0.0,
        "top_slot_is_max_value": float(np.mean(top_is_max)) if top_is_max else float("nan"),
        "top_slot_is_min_boost": float(np.mean(top_is_min_boost))
        if top_is_min_boost
        else float("nan"),
        "slot_base_vs_boost_spearman": bootstrap_ci(spearman_boost_slot),
    }


def ownership_skew_by_rank(lb: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    """Mean within-slate drafts percentile of rostered players, by rank band.

    Players absent from the observed label pool get NaN (not zero): the
    platform's sections under-surface low-ownership players, so a missing
    drafts value is itself informative and is counted separately.
    """
    picks = explode_leaderboards(lb)
    if picks.empty:
        return pd.DataFrame()
    pool = dedupe_pool(labels)
    pool = pool.assign(drafts_pct=pool.groupby("slate_date")["drafts"].rank(pct=True))
    merged = picks.merge(
        pool[["slate_date", "platform_player_id", "drafts_pct"]],
        left_on=["slate_date", "player_id"],
        right_on=["slate_date", "platform_player_id"],
        how="left",
    )
    merged["band"] = pd.cut(merged["rank"], [0, 1, 5, 10, 20], labels=["1", "2-5", "6-10", "11-20"])
    return (
        merged.groupby("band", observed=True)
        .agg(
            picks=("player_id", "size"),
            drafts_pct_mean=("drafts_pct", "mean"),
            unobserved_share=("drafts_pct", lambda s: float(s.isna().mean())),
            boost_mean=("boost", "mean"),
        )
        .reset_index()
    )


def repeat_finisher_comparison(
    lb: pd.DataFrame, labels: pd.DataFrame, *, min_appearances: int = 3, min_group: int = 30
) -> dict[str, Any]:
    """Repeat top-20 users vs one-time top-20 users.

    Gated: returns ``{"gated": True}`` unless both groups have at least
    ``min_group`` entries, so a handful of repeat users cannot produce a
    headline "smart money" signal. Compares per-entry mean drafts
    percentile and mean boost; reports a Welch t statistic for each.
    """
    picks = explode_leaderboards(lb)
    if picks.empty:
        return {"gated": True, "reason": "no parseable entries"}
    pool = dedupe_pool(labels)
    pool = pool.assign(drafts_pct=pool.groupby("slate_date")["drafts"].rank(pct=True))
    picks = picks.merge(
        pool[["slate_date", "platform_player_id", "drafts_pct"]],
        left_on=["slate_date", "player_id"],
        right_on=["slate_date", "platform_player_id"],
        how="left",
    )
    entry = (
        picks.groupby(["slate_date", "user_token", "rank"])
        .agg(drafts_pct=("drafts_pct", "mean"), boost=("boost", "mean"))
        .reset_index()
    )
    appearances = entry.groupby("user_token")["slate_date"].nunique()
    repeat_users = set(appearances[appearances >= min_appearances].index)
    entry["group"] = np.where(entry["user_token"].isin(repeat_users), "repeat", "other")
    counts = entry["group"].value_counts().to_dict()
    result: dict[str, Any] = {
        "n_repeat_users": len(repeat_users),
        "entries_by_group": {str(k): int(v) for k, v in counts.items()},
        "max_appearances": int(appearances.max()) if len(appearances) else 0,
    }
    if counts.get("repeat", 0) < min_group or counts.get("other", 0) < min_group:
        result.update(gated=True, reason=f"fewer than {min_group} entries in a group")
        return result
    for col in ("drafts_pct", "boost"):
        a = entry.loc[entry["group"] == "repeat", col].dropna()
        b = entry.loc[entry["group"] == "other", col].dropna()
        se = math.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
        result[col] = {
            "repeat_mean": float(a.mean()),
            "other_mean": float(b.mean()),
            "welch_t": float((a.mean() - b.mean()) / se) if se > 0 else float("nan"),
        }
    result["gated"] = False
    return result


def top20_duplication(lb: pd.DataFrame) -> dict[str, Any]:
    """Within-slate overlap among top-20 lineups (player sets, order ignored).

    ``exact_duplicate_share``: entries whose 5-player set appears more than
    once in the same slate's top 20. ``mean_pairwise_overlap``: average
    shared players between two top-20 entries on a slate (0-5).
    """
    exact, overlaps = [], []
    for _, s in lb.groupby("slate_date"):
        sets = []
        for raw in s["lineup"]:
            try:
                sets.append(frozenset(int(p["player_id"]) for p in parse_lineup(raw)))
            except (ValueError, KeyError, TypeError, json.JSONDecodeError):
                continue
        if len(sets) < 2:
            continue
        c = Counter(sets)
        exact.append(sum(n for n in c.values() if n > 1) / len(sets))
        overlaps.append(float(np.mean([len(a & b) for a, b in itertools.combinations(sets, 2)])))
    return {
        "n_slates": len(exact),
        "exact_duplicate_share": bootstrap_ci(exact),
        "mean_pairwise_overlap": bootstrap_ci(overlaps),
    }


def estimator_alignment(labels: pd.DataFrame) -> dict[str, Any]:
    """Does field.py's fallback ownership estimator rank players like the field?

    ``_estimated_ownership_unnormalized`` is a monotone softmax of
    ``pred_real_score * (1 + card_boost)`` (before small multiplicative
    flags), so its within-slate rank order equals the rank order of that
    product. Using the *realized* real_score as the prediction is the most
    favorable case for the estimator (a perfect point forecast); if even
    that proxy is anti-correlated with measured drafts, the live estimator
    is very likely anti-correlated too. Per slate, slate-bootstrap CI.
    """
    df = dedupe_pool(labels.dropna(subset=["drafts", "real_score"]))
    proxy, boost_only, score_only = [], [], []
    for _, s in df.groupby("slate_date"):
        if len(s) < 5:
            continue
        proxy.append(spearman(s["drafts"], s["real_score"] * (1.0 + s["card_boost"])))
        boost_only.append(spearman(s["drafts"], s["card_boost"]))
        score_only.append(spearman(s["drafts"], s["real_score"]))
    finite = [p for p in proxy if not math.isnan(p)]
    return {
        "n_slates": len(proxy),
        "drafts_vs_estimator_proxy": bootstrap_ci(proxy),
        "drafts_vs_card_boost": bootstrap_ci(boost_only),
        "drafts_vs_real_score": bootstrap_ci(score_only),
        "share_slates_proxy_negative": float(np.mean([p < 0 for p in finite]))
        if finite
        else float("nan"),
    }


def prior_slate_ownership_signal(labels: pd.DataFrame) -> dict[str, Any]:
    """How well a leak-free measured prior predicts today's ownership (#289).

    For each (slate, player) in the observed pool, take that player's drafts
    percentile on their most recent *earlier* slate (never the same slate,
    which is post-lock information a live freeze does not have) and
    correlate it with today's percentile. Compare against the estimator
    proxy from ``estimator_alignment`` on the same rows. Percentiles are
    within-slate so slate size and field size cancel.
    """
    df = dedupe_pool(labels.dropna(subset=["drafts"])).copy()
    df["drafts_pct"] = df.groupby("slate_date")["drafts"].rank(pct=True)
    df = df.sort_values(["platform_player_id", "slate_date"])
    df["prior_pct"] = df.groupby("platform_player_id")["drafts_pct"].shift(1)
    df["prior_date"] = df.groupby("platform_player_id")["slate_date"].shift(1)
    paired = df.dropna(subset=["prior_pct"])
    paired = paired[paired["prior_date"] < paired["slate_date"]]
    per_slate_prior, per_slate_proxy = [], []
    for _, s in paired.groupby("slate_date"):
        if len(s) < 5:
            continue
        per_slate_prior.append(spearman(s["prior_pct"], s["drafts_pct"]))
        if "real_score" in s and s["real_score"].notna().all():
            per_slate_proxy.append(
                spearman(s["real_score"] * (1.0 + s["card_boost"]), s["drafts_pct"])
            )
    return {
        "n_pairs": len(paired),
        "n_slates": len(per_slate_prior),
        "coverage_share_of_pool": float(len(paired) / len(df)) if len(df) else float("nan"),
        "prior_slate_pct_vs_today_pct": bootstrap_ci(per_slate_prior),
        "estimator_proxy_vs_today_pct_same_rows": bootstrap_ci(per_slate_proxy),
    }


def regime_split(gaps: pd.DataFrame, knobs: pd.DataFrame, knob: str) -> pd.DataFrame:
    """Committed-vs-winner share, split by one serving knob's value.

    Descriptive only: regimes are not randomized and differ in calendar
    window, so a difference here is not an effect estimate.
    """
    if gaps.empty or knobs.empty:
        return pd.DataFrame()
    m = gaps.merge(knobs[["slate_date", knob]], on="slate_date", how="left")
    m = m[m["committed_exact"] & m["field_exact"]].copy()
    m[knob] = [("unrecorded" if v is None or v != v else str(v)) for v in m[knob]]
    m["share"] = m["committed"] / m["field_best"]
    return (
        m.groupby(knob)
        .agg(n=("share", "size"), committed_share_of_winner=("share", "mean"))
        .reset_index()
    )


# ---------------------------------------------------------------------------
# Section C: dossier gaps and serving knobs
# ---------------------------------------------------------------------------


def dossier_gap_table(dossiers: Mapping[str, Mapping[str, Any]]) -> pd.DataFrame:
    rows = []
    for sd, d in sorted(dossiers.items()):
        e = d.get("entries", {})
        c, f, t = e.get("committed", {}), e.get("field_best", {}), e.get("theoretical_ceiling", {})
        if not f or not t:
            continue
        rows.append(
            {
                "slate_date": sd,
                "committed": c.get("score"),
                "committed_exact": c.get("censor_reason") is None,
                "field_best": f.get("score"),
                "field_exact": f.get("censor_reason") is None,
                "ceiling": t.get("score"),
                "ceiling_labels_complete": t.get("censor_reason") is None,
            }
        )
    return pd.DataFrame(rows)


def dossier_gap_summary(table: pd.DataFrame) -> dict[str, Any]:
    """Winner-vs-ceiling and committed-vs-winner, on exact rows only.

    ``winner_share_of_ceiling`` > 1 can occur because the ceiling is drawn
    from the observed label pool only (players absent from the community
    sections cannot enter it) and is pruned; those rows are counted, not
    hidden.
    """
    if table.empty:
        return {"n": 0}
    fw = table[table["field_exact"]].copy()
    fw["share"] = fw["field_best"] / fw["ceiling"]
    near = fw[fw["share"] >= 0.95]
    cm = table[table["committed_exact"] & table["field_exact"]].copy()
    cm["gap"] = cm["field_best"] - cm["committed"]
    cm["share"] = cm["committed"] / cm["field_best"]
    return {
        "n_dossiers": len(table),
        "n_field_exact": len(fw),
        "winner_share_of_ceiling": bootstrap_ci(fw["share"].tolist()),
        "winner_within_5pct_of_ceiling": float(len(near) / len(fw)) if len(fw) else float("nan"),
        "winner_exceeds_observed_ceiling": int((fw["share"] > 1.0).sum()),
        "ceiling_gap_points": bootstrap_ci((fw["ceiling"] - fw["field_best"]).tolist()),
        "n_committed_exact": len(cm),
        "committed_share_of_winner": bootstrap_ci(cm["share"].tolist()),
        "committed_gap_points": bootstrap_ci(cm["gap"].tolist()),
        "winner_score": bootstrap_ci(fw["field_best"].tolist()),
    }


def winner_vs_own_distribution(
    gaps: pd.DataFrame, lineups: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    """Where the field winner sits against our own frozen score distribution.

    Uses ``lineup_score_p10/p50/p90`` recorded at freeze time. Answers
    task-doc question 5: what percentile of our own simulated outcome would
    have had to land to match the winner, historically. Also reports the
    calibration of that distribution against our own realized committed
    score (exact rows only): a calibrated p10/p90 band contains ~80%.
    Freezes with a non-positive p50 or p90 are skipped (degenerate record).
    """
    rows = []
    for rec in gaps.itertuples(index=False):
        lineup = (lineups.get(rec.slate_date) or {}).get("lineup")
        if not isinstance(lineup, dict):
            continue
        try:
            p10 = float(lineup["lineup_score_p10"])
            p50 = float(lineup["lineup_score_p50"])
            p90 = float(lineup["lineup_score_p90"])
        except (KeyError, TypeError, ValueError):
            continue
        if p50 <= 0 or p90 <= 0:
            continue
        rows.append(
            {
                "winner": float(rec.field_best),
                "committed": float(rec.committed) if rec.committed_exact else float("nan"),
                "p10": p10,
                "p50": p50,
                "p90": p90,
            }
        )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return {"n": 0}
    own = frame.dropna(subset=["committed"])
    return {
        "n": len(frame),
        "share_winner_above_our_p90": float((frame["winner"] > frame["p90"]).mean()),
        "share_winner_above_our_p50": float((frame["winner"] > frame["p50"]).mean()),
        "winner_over_our_p90": bootstrap_ci((frame["winner"] / frame["p90"]).tolist()),
        "winner_over_our_p50": bootstrap_ci((frame["winner"] / frame["p50"]).tolist()),
        "n_committed_exact": len(own),
        "committed_below_our_p10": float((own["committed"] < own["p10"]).mean())
        if len(own)
        else float("nan"),
        "committed_below_our_p50": float((own["committed"] < own["p50"]).mean())
        if len(own)
        else float("nan"),
        "committed_above_our_p90": float((own["committed"] > own["p90"]).mean())
        if len(own)
        else float("nan"),
    }


def serving_knob_history(lineups: Mapping[str, Mapping[str, Any]]) -> pd.DataFrame:
    """Per-slate objective knobs the frozen lineup actually ran with.

    Reads ``lineup.serving_knobs`` (written by job2's freeze since D90) and
    the row's ``payout_regime``. Missing knobs stay None rather than being
    filled from code defaults, so earlier freezes read as unrecorded.
    """
    rows = []
    for sd, rec in sorted(lineups.items()):
        lineup = rec.get("lineup")
        knobs = (lineup.get("serving_knobs") if isinstance(lineup, dict) else None) or {}
        row: dict[str, Any] = {
            "slate_date": sd,
            "has_serving_knobs": bool(knobs),
            "payout_regime": rec.get("payout_regime"),
        }
        for k in SERVING_KNOBS:
            row[k] = knobs.get(k)
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_knob_history(history: pd.DataFrame) -> dict[str, Any]:
    if history.empty:
        return {"n": 0}
    out: dict[str, Any] = {
        "n_lineups": len(history),
        "with_serving_knobs": int(history["has_serving_knobs"].sum()),
    }
    for k in ("payout_regime", *SERVING_KNOBS):
        col = history[k].dropna()
        if col.empty:
            out[k] = "absent"
            continue
        runs = []
        prev = object()
        for sd, v in zip(history.loc[col.index, "slate_date"], col, strict=True):
            if v != prev:
                runs.append({"from": sd, "value": v})
                prev = v
        out[k] = runs
    return out


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _jsonable(obj: Any) -> Any:
    if isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient="records")
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        return None if math.isnan(float(obj)) else round(float(obj), 4)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


def run(args: argparse.Namespace) -> dict[str, Any]:
    report: dict[str, Any] = defaultdict(dict)
    labels = load_labels(args.labels_csv)
    window = labels[labels["slate_date"] >= args.since]
    report["A"]["labels"] = audit_labels(labels, args.since)
    report["B"]["popularity_value_correlation"] = popularity_value_correlation(window)
    report["B"]["half_split_low_over_high_value"] = half_split_value_ratio(window)
    report["B"]["ownership_estimator_alignment"] = estimator_alignment(window)
    report["B"]["prior_slate_ownership_signal"] = prior_slate_ownership_signal(window)
    membership = ceiling_popularity_membership(window)
    membership.pop("per_slate", None)
    report["B"]["ceiling_popularity_membership"] = membership

    if args.leaderboards_csv:
        lb = load_leaderboards(args.leaderboards_csv)
        lbw = lb[lb["slate_date"] >= args.since]
        report["A"]["leaderboards"] = audit_leaderboards(lb, args.since)
        report["B"]["slot_order_profile"] = slot_order_profile(lbw)
        report["B"]["ownership_skew_by_rank"] = ownership_skew_by_rank(lbw, window)
        report["B"]["repeat_finishers"] = repeat_finisher_comparison(lbw, window)
        report["B"]["top20_duplication"] = top20_duplication(lbw)
    else:
        report["A"]["leaderboards"] = "not provided (--leaderboards-csv)"

    gaps = pd.DataFrame()
    if args.dossier_dir:
        dossiers = {k: v for k, v in load_json_dir(args.dossier_dir).items() if k >= args.since}
        report["A"]["dossier_coverage"] = dossier_coverage(dossiers, window["slate_date"].unique())
        gaps = dossier_gap_table(dossiers)
        report["C"]["dossier_gaps"] = dossier_gap_summary(gaps)
    if args.lineup_dir:
        lineups = {k: v for k, v in load_json_dir(args.lineup_dir).items() if k >= args.since}
        history = serving_knob_history(lineups)
        report["C"]["serving_knobs"] = summarize_knob_history(history)
        report["C"]["committed_share_by_leverage_weight"] = regime_split(
            gaps, history, "leverage_weight"
        )
        report["C"]["winner_vs_own_distribution"] = winner_vs_own_distribution(gaps, lineups)
    return _jsonable(dict(report))


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--labels-csv", type=pathlib.Path, required=True)
    p.add_argument("--leaderboards-csv", type=pathlib.Path)
    p.add_argument("--dossier-dir", type=pathlib.Path)
    p.add_argument("--lineup-dir", type=pathlib.Path)
    p.add_argument("--since", default=DEFAULT_SINCE)
    p.add_argument("--json-out", type=pathlib.Path)
    args = p.parse_args(argv)
    report = run(args)
    text = json.dumps(report, indent=2, default=str)
    if args.json_out:
        args.json_out.write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
