"""Serve-time enrichment schema (pandera[polars]).

Validates the ``job1_enrichment`` rows job2 reads at freeze time. The
validator catches the failure modes the row-count watchdog checks miss:

- ``position`` field silently normalized to a single value across the
  whole pool (2026-07-02 shape, all rows "G")
- ``card_boost`` outside the Real Sports 0.0-3.5 platform range
- ``vegas_total`` present but zero for a majority of the pool (odds
  scrape half-degraded but not fully empty)
- ``recent_minutes`` / ``per_min_rate`` present on <20% of the pool
  (minutes feed regressed but head_features join still fired)
- ``rotowire_confirmed`` never true on a whole slate (D107 shape)

Rollout is warn-only: each finding emits a ``schema_finding`` diagnostic
that job2 can persist as a watchdog event (SEVERITY_WARN) and continue
freezing. Once the counts stay at zero for a rolling week, the caller
can promote failures to raise.

Design: pandera works on a per-row DataFrame; the JSONB features_json
column is flattened into a small side-frame keyed by player_id + the
handful of features_json fields job2 actually reads. Anything the
scoring path doesn't consume is not validated here -- pandera's job is
guard the read boundary, not audit the whole payload.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SchemaFinding:
    """One violation the validator surfaces. ``severity`` is always
    ``warn`` today; the caller decides whether to escalate."""

    trigger: str
    payload: dict[str, Any]


_ALLOWED_POSITIONS = {"G", "F", "C", "G-F", "F-G", "F-C", "C-F", ""}


def _features_dict(raw: object) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, (bytes, str)) and raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return {}


def _flatten_enrichment(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Row-per-player shape the pandera schema validates. Keeps only the
    top-level columns + the features_json fields the scoring path reads,
    coerced to native Python types so pandera/polars infers a stable schema."""
    out: list[dict[str, Any]] = []
    for r in rows:
        f = _features_dict(r.get("features_json"))
        try:
            pid = int(r.get("real_sports_player_id") or 0)
        except (TypeError, ValueError):
            pid = 0
        try:
            boost = float(r.get("card_boost") or 0.0)
        except (TypeError, ValueError):
            boost = 0.0
        rec: dict[str, Any] = {
            "player_id": pid,
            "team": str(r.get("team") or ""),
            "opponent": str(r.get("opponent") or ""),
            "position": str(r.get("position") or ""),
            "card_boost": boost,
            "vegas_total": float(f.get("vegas_total", 0.0) or 0.0),
            "is_out": int(f.get("is_out", 0) or 0),
            "is_starter": int(f.get("is_starter", 0) or 0),
            "rotowire_confirmed": int(f.get("rotowire_confirmed", 0) or 0),
            "recent_minutes": (
                float(f["recent_minutes"]) if f.get("recent_minutes") is not None else None
            ),
            "per_min_rate": (
                float(f["per_min_rate"]) if f.get("per_min_rate") is not None else None
            ),
            "prop_over_prob": (
                float(f["prop_points_over_prob"])
                if f.get("prop_points_over_prob") is not None
                else None
            ),
            "head_features_present": bool(f.get("head_features")),
        }
        out.append(rec)
    return out


def validate_enrichment(
    enrichment_rows: list[dict[str, Any]],
    *,
    strict: bool = False,
) -> list[SchemaFinding]:
    """Check the flattened enrichment for the failure modes documented
    above. Returns a list of findings (empty when the pool is healthy).

    ``strict=False`` returns findings; the caller decides what to do.
    ``strict=True`` raises ``ValueError`` on any finding, useful for
    tests that want a hard boundary. Rollout ships with strict=False.
    """
    findings: list[SchemaFinding] = []
    if not enrichment_rows:
        return findings
    flat = _flatten_enrichment(enrichment_rows)
    n = len(flat)

    # Per-row hard rejections (only structural: card_boost outside [0, 5]
    # or unknown position are ingest bugs, not feature-degradation).
    bad_boost = [r for r in flat if r["card_boost"] < 0.0 or r["card_boost"] > 5.0]
    if bad_boost:
        findings.append(
            SchemaFinding(
                trigger="schema_card_boost_out_of_range",
                payload={
                    "n_rows": n,
                    "n_bad": len(bad_boost),
                    "sample_pids": [r["player_id"] for r in bad_boost[:5]],
                },
            )
        )
    unknown_pos = [r for r in flat if r["position"] not in _ALLOWED_POSITIONS]
    if unknown_pos:
        findings.append(
            SchemaFinding(
                trigger="schema_unknown_position",
                payload={
                    "n_rows": n,
                    "n_bad": len(unknown_pos),
                    "sample": [
                        {"pid": r["player_id"], "position": r["position"]} for r in unknown_pos[:5]
                    ],
                },
            )
        )

    # Pool-wide degeneracies. These are the 2026-07-02 signature.
    distinct_positions = {r["position"] for r in flat if r["position"]}
    if n >= 10 and len(distinct_positions) < 2:
        # All players collapsed to one position (or blank) -- the
        # ingest lost the position mapping. The picker still runs but
        # every player is effectively interchangeable at scoring time.
        findings.append(
            SchemaFinding(
                trigger="schema_position_collapsed",
                payload={
                    "n_rows": n,
                    "distinct_positions": sorted(distinct_positions) or ["<empty>"],
                    "note": (
                        "position field degenerate across the pool; ingest join "
                        "into RotoWire / Real Sports likely lost the mapping."
                    ),
                },
            )
        )

    # Minutes feed presence. If <20% of the pool has recent_minutes, the
    # minutes head goes dark and the fallback dominates.
    with_minutes = sum(1 for r in flat if r["recent_minutes"] is not None)
    if n >= 10 and with_minutes / n < 0.20:
        findings.append(
            SchemaFinding(
                trigger="schema_minutes_feed_sparse",
                payload={
                    "n_rows": n,
                    "with_minutes": with_minutes,
                    "coverage": round(with_minutes / n, 3),
                    "threshold": 0.20,
                },
            )
        )

    with_head = sum(1 for r in flat if r["head_features_present"])
    if n >= 10 and with_head / n < 0.20:
        findings.append(
            SchemaFinding(
                trigger="schema_head_features_sparse",
                payload={
                    "n_rows": n,
                    "with_head": with_head,
                    "coverage": round(with_head / n, 3),
                    "threshold": 0.20,
                    "note": (
                        "Fewer than 20% of the pool has head_features; "
                        "the Tier-0 head predict path will fall through to heuristic."
                    ),
                },
            )
        )

    # Vegas coverage: a fully-empty odds feed is already handled by
    # watchdog._check_feature_content. Add the middle-ground signal: rows
    # exist AND >10% of the pool has zero vegas_total (partial odds).
    zero_vegas = sum(1 for r in flat if r["vegas_total"] == 0.0)
    if n >= 10 and 0.10 <= zero_vegas / n < 1.0:
        findings.append(
            SchemaFinding(
                trigger="schema_vegas_partial_gap",
                payload={
                    "n_rows": n,
                    "n_zero_vegas": zero_vegas,
                    "coverage_missing": round(zero_vegas / n, 3),
                    "threshold": 0.10,
                    "note": "partial odds coverage; game-script tilt degraded for some players.",
                },
            )
        )

    # Prop probability sanity: values outside [0, 1] indicate a scrape
    # coercion bug (prob left as a %-string). Not the [0, 1] side-quest;
    # a hard structural check.
    bad_prob = [
        r for r in flat if r["prop_over_prob"] is not None and not 0.0 <= r["prop_over_prob"] <= 1.0
    ]
    if bad_prob:
        findings.append(
            SchemaFinding(
                trigger="schema_prop_prob_out_of_range",
                payload={
                    "n_rows": n,
                    "n_bad": len(bad_prob),
                    "sample": [
                        {"pid": r["player_id"], "prob": r["prop_over_prob"]} for r in bad_prob[:5]
                    ],
                },
            )
        )

    if strict and findings:
        raise ValueError(f"serving-enrichment schema failed: {[f.trigger for f in findings]}")
    return findings
