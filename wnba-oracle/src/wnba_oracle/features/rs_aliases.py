"""Real Sports leaf-key → WNBA own-model feature aliases (#523 / #526).

Mirrors NFL naming. Same-slate HV / box finals stay leakage-blocked.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Mapping
from typing import Any, Final, Literal

RS_FEATURE_ALIASES: Final[dict[str, str]] = {
    "overallRank": "overall_rank",
    "baseBoostedValue": "base_boosted_value",
    "injuryBodyPart": "injury_body_part",
    "didNotPlay": "did_not_play",
    "started": "started",
    "minutes": "minutes",
    "awayMoneyline": "away_moneyline",
    "homeMoneyline": "home_moneyline",
    "lastTenWins": "last_ten_wins",
    "score": "draft_stats_score",
    "rank": "draft_stats_rank",
}

LEAKAGE_BLOCKED_SAME_SLATE: Final[frozenset[str]] = frozenset(
    {
        "base_boosted_value",
        "draft_stats_score",
        "draft_stats_rank",
        "did_not_play",
        "started",
        "minutes",
    }
)

RS_POOL_HEAD_FEATURES: Final[tuple[str, ...]] = (
    "overall_rank",
    "injury_body_part_hash",
    "injury_body_part_available",
    "team_moneyline",
    "opponent_moneyline",
    "moneyline_available",
    "last_ten_wins",
)

LeakageMode = Literal["live_ok", "historical_prior"]


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        try:
            if value is None or value == "":
                return None
            parsed = float(value)
        except (TypeError, ValueError):
            return None
    else:
        parsed = float(value)
    return parsed if math.isfinite(parsed) else None


def _bool01(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return 1.0 if float(value) else 0.0
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return 1.0
    if text in {"0", "false", "no", "n"}:
        return 0.0
    return None


def hash_categorical(value: str | None, *, buckets: int = 32) -> tuple[float, float]:
    text = re.sub(r"\s+", " ", (value or "").strip().lower())
    if not text:
        return 0.0, 0.0
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:4], "big") % max(1, buckets)
    return float(bucket), 1.0


def extract_overall_rank(raw: Mapping[str, Any] | None) -> dict[str, float]:
    if not isinstance(raw, Mapping):
        return {}
    rank = _finite(raw.get("overallRank"))
    if rank is None:
        return {}
    return {"overall_rank": rank}


def extract_injury_body_part(value: str | None) -> dict[str, float]:
    bucket, available = hash_categorical(value)
    if not available:
        return {"injury_body_part_hash": 0.0, "injury_body_part_available": 0.0}
    return {
        "injury_body_part_hash": bucket,
        "injury_body_part_available": available,
    }


def extract_moneyline_priors(
    *,
    home_moneyline: Any,
    away_moneyline: Any,
    is_home: bool,
) -> dict[str, float]:
    home = _finite(home_moneyline)
    away = _finite(away_moneyline)
    if home is None and away is None:
        return {"moneyline_available": 0.0}
    team = home if is_home else away
    opp = away if is_home else home
    out: dict[str, float] = {"moneyline_available": 1.0}
    if team is not None:
        out["team_moneyline"] = team
    if opp is not None:
        out["opponent_moneyline"] = opp
    return out


def extract_last_ten_wins(standings: Mapping[str, Any] | None) -> dict[str, float]:
    if not isinstance(standings, Mapping):
        return {}
    wins = _finite(standings.get("lastTenWins"))
    if wins is None:
        return {}
    return {"last_ten_wins": wins}


def extract_season_averages(season_averages: Mapping[str, Any] | None) -> dict[str, float]:
    if not isinstance(season_averages, Mapping) or not season_averages:
        return {}
    out: dict[str, float] = {}
    for key, value in season_averages.items():
        num = _finite(value)
        if num is None:
            continue
        snake = re.sub(r"[^a-z0-9]+", "_", str(key).strip().lower()).strip("_")
        if snake:
            out[f"season_avg_{snake}"] = num
    return out


def extract_box_participation(
    box: Mapping[str, Any] | None,
    *,
    mode: LeakageMode,
) -> dict[str, float]:
    if mode == "live_ok" or not isinstance(box, Mapping):
        return {}
    out: dict[str, float] = {}
    dnp = _bool01(box.get("didNotPlay"))
    if dnp is not None:
        out["prior_did_not_play"] = dnp
    started = _bool01(box.get("started"))
    if started is not None:
        out["prior_started"] = started
    minutes = _finite(box.get("minutes"))
    if minutes is not None:
        out["prior_minutes"] = minutes
    return out


def extract_draft_stats_row(
    row: Mapping[str, Any] | None,
    *,
    mode: LeakageMode,
) -> dict[str, float]:
    if not isinstance(row, Mapping) or mode == "live_ok":
        return {}
    out: dict[str, float] = {}
    base = _finite(row.get("baseBoostedValue"))
    if base is not None:
        out["prior_base_boosted_value"] = base
    score = _finite(row.get("score"))
    if score is not None:
        out["prior_draft_stats_score"] = score
    rank = _finite(row.get("rank"))
    if rank is not None:
        out["prior_draft_stats_rank"] = rank
    return out


def extract_pool_card_features(
    player: Mapping[str, Any] | None,
    *,
    injury_body_part: str | None = None,
) -> dict[str, float]:
    if not isinstance(player, Mapping):
        player = {}
    out: dict[str, float] = {}
    out.update(extract_overall_rank(player))
    body = injury_body_part
    if body is None:
        raw_body = player.get("injuryBodyPart")
        body = str(raw_body) if raw_body is not None else None
    out.update(extract_injury_body_part(body))
    return out
