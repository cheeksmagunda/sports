"""Real Sports exposed-field → own-model map for NFL (#523 / #526).

Durable inventory of provider surfaces we scrape or plan to dump into the
separate corpus. Status vocabulary matches the operator matrix:

- mapped: live_ok and consumed by recommendations.model / FeatureDrivenValueModel
- gap: exposed / known but not yet in the own-model design matrix
- leakage-blocked: post-settlement / same-slate finals (never live features)
- unused: captured or documented but deliberately not modeled yet
- label: Highest-value / Total Value board target (not a feature)

Never treat winning drafts as the primary train target.
"""

from __future__ import annotations

from typing import Literal

RsStatus = Literal["mapped", "gap", "leakage-blocked", "unused", "label"]

# (rs_field, ingest_path, durable_store, own_model_slot, status)
RS_FIELD_MATRIX: tuple[tuple[str, str, str, str, RsStatus], ...] = (
    (
        "playerBoxScores[].value",
        "ingest/corpus_g stats",
        "corpus_g / ValueLabel.value",
        "train label (valuelaw / ridge target)",
        "label",
    ),
    (
        "highestBoostedValuePlayers",
        "contest finalized stats / draftStats",
        "corpus HV boards (#526)",
        "high-TV sample weights / grade label",
        "label",
    ),
    (
        "overallRank",
        "recommendations.provider Candidate + context",
        "context_features overall_rank",
        "REQUIRED_RS_POOL_CONTEXT_FEATURES",
        "mapped",
    ),
    (
        "injuryBodyPart",
        "recommendations.provider + context hash",
        "context_features injury_body_part_hash",
        "REQUIRED_RS_POOL_CONTEXT_FEATURES",
        "mapped",
    ),
    (
        "homeMoneyline / awayMoneyline",
        "day content Game + context",
        "context_features team/opponent_moneyline",
        "REQUIRED_RS_POOL_CONTEXT_FEATURES",
        "mapped",
    ),
    (
        "lastTenWins",
        "gameTeamComparison standings / Game priors",
        "context_features last_ten_wins",
        "REQUIRED_RS_POOL_CONTEXT_FEATURES",
        "mapped",
    ),
    (
        "didNotPlay / started / minutes (prior box)",
        "Corpus G box → prior_* only",
        "context_features prior_*",
        "REQUIRED_RS_POOL_CONTEXT_FEATURES",
        "mapped",
    ),
    (
        "seasonAverages.*",
        "game feed players",
        "extract_season_averages (not called on freeze context)",
        "UNUSED_GOLD pending Candidate.season_averages wiring",
        "unused",
    ),
    (
        "baseBoostedValue / draftStats score/rank (same slate)",
        "contest draftStats HV",
        "label / prior_* only",
        "LEAKAGE_BLOCKED_SAME_SLATE",
        "leakage-blocked",
    ),
    (
        "draftStats[]",
        "contest /games/.../stats",
        "corpus contest dump (#526)",
        "offline replay only until HV parsed",
        "gap",
    ),
    (
        "card boost / multiplierBonus (pre-lock pool)",
        "recommendations pool + contests.boosts",
        "decision snapshot / BoostObservation",
        "optimizer score; not ridge float",
        "mapped",
    ),
    (
        "injuryStatus",
        "recommendations.context injury_indicator_features",
        "context_features injury_*",
        "REQUIRED_LIVE_OK_CONTEXT_FEATURES",
        "mapped",
    ),
    (
        "home/away + opponent (schedule/slate)",
        "recommendations.context + schedule",
        "context_features is_home/home_away/is_divisional",
        "REQUIRED_SLATE_CONTEXT_FEATURES",
        "mapped",
    ),
    (
        "kickoff datetime → kickoff_slot",
        "recommendations.context kickoff_slot_features",
        "context_features kickoff_slot_*",
        "REQUIRED_SLATE_CONTEXT_FEATURES",
        "mapped",
    ),
    (
        "NWS weather magnitudes",
        "features.live weather_features",
        "context_features weather_*",
        "REQUIRED_LIVE_OK_CONTEXT_FEATURES",
        "mapped",
    ),
    (
        "opponent defense / pace priors",
        "features.opponent_defense + context",
        "context_features opp_*/pace_*",
        "REQUIRED_SLATE_CONTEXT_FEATURES",
        "mapped",
    ),
    (
        "gameBoxScore / teamBoxScores / periods",
        "ingest/corpus_g stats",
        "corpus_g raw + redacted artifacts",
        "pace/defense priors (historical)",
        "mapped",
    ),
    (
        "gameTeamComparison standings / previousMeetings",
        "ingest/corpus_g stats",
        "corpus dump every key (#526)",
        "unused pending research encoding",
        "unused",
    ),
    (
        "same-slate ownership / Drafts / post-lock boxes",
        "live forbidden",
        "n/a",
        "LIVE_FEATURE_BLACKLIST",
        "leakage-blocked",
    ),
    (
        "contest leaderboard winning drafts",
        "forbidden primary target",
        "n/a",
        "never train primary",
        "leakage-blocked",
    ),
    (
        "feed rankings / search pool rows",
        "provider feed + pool capture",
        "corpus dump (#526)",
        "identity + pool membership",
        "mapped",
    ),
    (
        "boostControl / draftInfo / payoutInfo fixtures",
        "contests corpus C paths",
        "fixtures + corpus dump",
        "optimizer / payout regime only",
        "unused",
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
