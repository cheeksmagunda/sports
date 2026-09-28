"""Real Sports exposed-field → own-model map for WNBA (#523 / #526).

Highest-value / Total Value boards are labels. LightGBM heads are optional
behind ``WNBA_SERVE_PRIMARY=heads``; default serve is EB.
"""

from __future__ import annotations

from typing import Literal

RsStatus = Literal["mapped", "gap", "leakage-blocked", "unused", "label"]

RS_FIELD_MATRIX: tuple[tuple[str, str, str, str, RsStatus], ...] = (
    (
        "highestBoostedValuePlayers / Total Value boards",
        "dayclose / contest finalized stats",
        "slate_labels + corpus HV (#526)",
        "train/grade label (never winning drafts)",
        "label",
    ),
    (
        "pool card_boost / multiplierBonus",
        "job1 enrichment",
        "job1_enrichment.card_boost",
        "EB boost_beta + picker score",
        "mapped",
    ),
    (
        "vegas_total / vegas_spread / implied_team_total",
        "job1 odds join → features_json / head_features",
        "job1_enrichment.features_json",
        "EB vegas_beta (+ monotone docs)",
        "mapped",
    ),
    (
        "is_confirmed_starter / starter_slot / RotoWire",
        "job1 / minutes_features",
        "features_json",
        "serve _starter_multiplier on EB",
        "mapped",
    ),
    (
        "team_pace / opp_pace / game_pace_implied",
        "serving_features / corpus rolling",
        "head_features",
        "EB pace + opp_pace betas",
        "mapped",
    ),
    (
        "mins_l5/l10 + rolling rates (_BASE_FEATURES)",
        "features.serving_features / corpus",
        "head_features",
        "minutes blend; LGBM optional",
        "mapped",
    ),
    (
        "ownership / Drafts (post-close)",
        "dayclose slate_labels",
        "slate_labels.drafts",
        "field estimator only; not EB float",
        "leakage-blocked",
    ),
    (
        "winning draft lineups",
        "forbidden primary target",
        "n/a",
        "never train primary",
        "leakage-blocked",
    ),
    (
        "overallRank / injuryBodyPart / moneylines / lastTenWins",
        "job1 pool + odds → head_features fuse",
        "head_features + EB rank/moneyline terms",
        "EBHierarchicalBaseline + fuse_slate_enrichment",
        "mapped",
    ),
    (
        "seasonAverages.*",
        "feed / pool when present",
        "head_features season_avg_* via FEATURE_MATRIX serve=on",
        "job1 apply_feature_matrix (#583)",
        "mapped",
    ),
    (
        "baseBoostedValue / draftStats score/rank (same slate)",
        "dayclose HV boards",
        "label / prior_* only",
        "LEAKAGE_BLOCKED_SAME_SLATE",
        "leakage-blocked",
    ),
    (
        "draftStats / popularPlayers / mostCommon3x",
        "contest finalized stats",
        "corpus dump every key (#526)",
        "offline replay / research",
        "gap",
    ),
    (
        "game logs box score keys",
        "nba_api + RS boxes",
        "wnba_game_logs / corpus",
        "rolling feature builders",
        "mapped",
    ),
)


def rs_field_matrix() -> list[dict[str, str]]:
    return [
        {
            "rs_field": rs,
            "ingest_path": ingest,
            "durable_store": store,
            "own_model_slot": slot,
            "status": status,
        }
        for rs, ingest, store, slot, status in RS_FIELD_MATRIX
    ]


def mapped_rs_field_count() -> int:
    return sum(1 for *_, status in RS_FIELD_MATRIX if status == "mapped")
