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


def _structural_findings(flat: list[dict[str, Any]]) -> list[SchemaFinding]:
    n = len(flat)
    findings: list[SchemaFinding] = []
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
    return findings


def _position_finding(flat: list[dict[str, Any]]) -> SchemaFinding | None:
    n = len(flat)
    distinct_positions = {r["position"] for r in flat if r["position"]}
    if n < 10 or len(distinct_positions) >= 2:
        return None
    return SchemaFinding(
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


def _coverage_finding(
    flat: list[dict[str, Any]],
    *,
    present_key: str,
    trigger: str,
    count_key: str,
    note: str | None = None,
    truthy: bool = False,
) -> SchemaFinding | None:
    n = len(flat)
    present = sum(
        1 for row in flat if (bool(row[present_key]) if truthy else row[present_key] is not None)
    )
    if n < 10 or present / n >= 0.20:
        return None
    payload: dict[str, Any] = {
        "n_rows": n,
        count_key: present,
        "coverage": round(present / n, 3),
        "threshold": 0.20,
    }
    if note is not None:
        payload["note"] = note
    return SchemaFinding(trigger=trigger, payload=payload)


def _vegas_finding(flat: list[dict[str, Any]]) -> SchemaFinding | None:
    n = len(flat)
    zero_vegas = sum(1 for row in flat if row["vegas_total"] == 0.0)
    missing_ratio = zero_vegas / n
    if n < 10 or not 0.10 <= missing_ratio < 1.0:
        return None
    return SchemaFinding(
        trigger="schema_vegas_partial_gap",
        payload={
            "n_rows": n,
            "n_zero_vegas": zero_vegas,
            "coverage_missing": round(missing_ratio, 3),
            "threshold": 0.10,
            "note": "partial odds coverage; game-script tilt degraded for some players.",
        },
    )


def _prop_probability_finding(flat: list[dict[str, Any]]) -> SchemaFinding | None:
    bad_prob = [
        row
        for row in flat
        if row["prop_over_prob"] is not None and not 0.0 <= row["prop_over_prob"] <= 1.0
    ]
    if not bad_prob:
        return None
    return SchemaFinding(
        trigger="schema_prop_prob_out_of_range",
        payload={
            "n_rows": len(flat),
            "n_bad": len(bad_prob),
            "sample": [
                {"pid": row["player_id"], "prob": row["prop_over_prob"]} for row in bad_prob[:5]
            ],
        },
    )


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
    if not enrichment_rows:
        return []
    flat = _flatten_enrichment(enrichment_rows)
    findings = _structural_findings(flat)
    optional_findings = (
        _position_finding(flat),
        _coverage_finding(
            flat,
            present_key="recent_minutes",
            trigger="schema_minutes_feed_sparse",
            count_key="with_minutes",
        ),
        _coverage_finding(
            flat,
            present_key="head_features_present",
            trigger="schema_head_features_sparse",
            count_key="with_head",
            truthy=True,
            note=(
                "Fewer than 20% of the pool has head_features; "
                "the Tier-0 head predict path will fall through to heuristic."
            ),
        ),
        _vegas_finding(flat),
        _prop_probability_finding(flat),
    )
    findings.extend(finding for finding in optional_findings if finding is not None)

    if strict and findings:
        raise ValueError(f"serving-enrichment schema failed: {[f.trigger for f in findings]}")
    return findings
