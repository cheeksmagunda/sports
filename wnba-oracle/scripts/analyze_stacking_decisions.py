"""Read-only analytics for durable contextual-stacking decisions.

The command selects one latest frozen lineup per slate and the latest placement
row for that slate from one verified, read-only, repeatable-read PostgreSQL
transaction. Placement rows are joined by slate date only because the current
schema does not link a placement to a frozen-lineup id. The output therefore
reports measurement coverage, never stack-policy wins, losses, ROI, or causal
performance claims.

Usage:
    uv run python scripts/analyze_stacking_decisions.py
    uv run python scripts/analyze_stacking_decisions.py --json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import statistics
import sys
import urllib.parse
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import create_engine, text

TRANSACTION_OPTIONS = (
    "-c default_transaction_read_only=on "
    "-c statement_timeout=60000 "
    "-c lock_timeout=5000 "
    "-c idle_in_transaction_session_timeout=120000"
)

ANALYTICS_QUERY = text(
    """
    WITH latest_freezes AS (
        SELECT DISTINCT ON (slate_date)
            id, slate_date, model_sha, freeze_seq, frozen_via,
            operation_key, frozen_at, lineup
        FROM frozen_lineups
        ORDER BY slate_date, frozen_at DESC, id DESC
    ),
    latest_placements AS (
        SELECT DISTINCT ON (slate_date)
            slate_date, recorded_at, source, entry_rank, entry_count,
            finish_percentile, metadata_json
        FROM contest_placements
        ORDER BY slate_date, recorded_at DESC, contest_id DESC
    )
    SELECT
        f.id AS frozen_lineup_id,
        f.slate_date::text AS slate_date,
        f.model_sha,
        f.freeze_seq,
        f.frozen_via,
        f.operation_key,
        f.frozen_at,
        f.lineup,
        p.recorded_at AS placement_recorded_at,
        p.source AS placement_source,
        p.entry_rank,
        p.entry_count,
        p.finish_percentile,
        p.metadata_json AS placement_metadata_json
    FROM latest_freezes AS f
    LEFT JOIN latest_placements AS p USING (slate_date)
    ORDER BY f.slate_date, f.id
    """
)


def _clean_url(raw: str) -> str:
    """Remove only matching outer quotes sometimes retained by dotenv tooling."""

    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _require_verified_tls(url: str) -> None:
    """Require server identity verification for a public database URL."""

    parsed = urllib.parse.urlsplit(url)
    query = {
        key.lower(): value.lower()
        for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    }
    if query.get("sslmode") not in {"verify-ca", "verify-full"}:
        raise ValueError("DATABASE_PUBLIC_URL must use sslmode=verify-ca or verify-full")


def _sqlalchemy_url(url: str) -> str:
    """Select the installed psycopg driver without exposing URL components."""

    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def _json_object(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, Mapping):
        return {str(key): value for key, value in raw.items()}
    if isinstance(raw, (bytes, str)):
        try:
            parsed = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
            return None
        if isinstance(parsed, Mapping):
            return {str(key): value for key, value in parsed.items()}
    return None


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if parsed >= 0 else None


def _positive_int(value: Any) -> int | None:
    parsed = _nonnegative_int(value)
    return parsed if parsed and parsed > 0 else None


def _nonnegative_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if math.isfinite(parsed) and parsed >= 0.0 else None


def _decision_from_row(row: Mapping[str, Any]) -> tuple[str, dict[str, Any] | None]:
    """Classify a row as versioned, legacy, or malformed instrumentation."""

    lineup = _json_object(row.get("lineup"))
    if not lineup or "stack_decision" not in lineup:
        return "legacy_uninstrumented", None
    decision = _json_object(lineup.get("stack_decision"))
    if decision is None:
        return "malformed_or_unversioned", None
    version = decision.get("policy_version")
    if not isinstance(version, str) or not version.strip():
        return "malformed_or_unversioned", decision
    return "versioned", decision


def _preferred_shape_status(decision: Mapping[str, Any]) -> str:
    """Return preferred, concentrated, or unknown from recorded composition."""

    selected_games = _nonnegative_int(decision.get("selected_game_count"))
    selected_teams = _nonnegative_int(decision.get("selected_team_count"))
    selected_max_game = _nonnegative_int(decision.get("selected_max_players_per_game"))
    preferred_min_games = _nonnegative_int(decision.get("preferred_min_games"))
    preferred_teams = _nonnegative_int(decision.get("preferred_team_count"))
    preferred_max_game = _nonnegative_int(decision.get("preferred_max_players_per_game"))
    required = (
        selected_games,
        selected_teams,
        selected_max_game,
        preferred_min_games,
        preferred_teams,
        preferred_max_game,
    )
    if any(value is None for value in required):
        return "unknown"
    preferred = (
        selected_games >= preferred_min_games
        and selected_teams >= preferred_teams
        and selected_max_game <= preferred_max_game
    )
    return "preferred" if preferred else "concentrated"


def _placement_status(row: Mapping[str, Any]) -> str:
    """Classify measurement coverage without inferring a success or failure."""

    if row.get("placement_recorded_at") is None:
        return "unknown"
    metadata = _json_object(row.get("placement_metadata_json")) or {}
    source = str(row.get("placement_source") or "")
    rank = _positive_int(row.get("entry_rank"))

    # Older automatic rows used 21 as a below-top-20 sentinel. It is not an
    # exact rank and cannot safely be promoted to censored without its bounds.
    if source == "auto_dayclose" and rank == 21:
        return "unknown"
    if rank is not None:
        return "exact"
    if metadata.get("cracked_captured_board") is False:
        return "censored"
    if any(
        metadata.get(key) is not None
        for key in (
            "rank_lower_bound",
            "finish_percentile_floor",
            "finish_percentile_lower_bound",
        )
    ):
        return "censored"
    return "unknown"


def _rate_table(counts: Counter[str], denominator: int) -> dict[str, dict[str, int | float]]:
    return {
        key: {
            "count": int(count),
            "rate": (float(count) / denominator if denominator else 0.0),
        }
        for key, count in sorted(counts.items())
    }


def _composition_summary(decisions: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    shape_counts: Counter[str] = Counter()
    selected_game_counts: Counter[str] = Counter()
    selected_team_counts: Counter[str] = Counter()
    selected_max_game_counts: Counter[str] = Counter()
    selected_max_team_counts: Counter[str] = Counter()
    for decision in decisions:
        shape_counts[_preferred_shape_status(decision)] += 1
        for field, target in (
            ("selected_game_count", selected_game_counts),
            ("selected_team_count", selected_team_counts),
            ("selected_max_players_per_game", selected_max_game_counts),
            ("selected_max_players_per_team", selected_max_team_counts),
        ):
            value = _nonnegative_int(decision.get(field))
            target[str(value) if value is not None else "unknown"] += 1

    determinate = shape_counts["preferred"] + shape_counts["concentrated"]
    return {
        "preferred": shape_counts["preferred"],
        "concentrated": shape_counts["concentrated"],
        "unknown": shape_counts["unknown"],
        "determinate_denominator": determinate,
        "preferred_rate": (shape_counts["preferred"] / determinate if determinate else 0.0),
        "concentrated_rate": (shape_counts["concentrated"] / determinate if determinate else 0.0),
        "selected_game_count": dict(sorted(selected_game_counts.items())),
        "selected_team_count": dict(sorted(selected_team_counts.items())),
        "selected_max_players_per_game": dict(sorted(selected_max_game_counts.items())),
        "selected_max_players_per_team": dict(sorted(selected_max_team_counts.items())),
    }


def _objective_sacrifice_summary(decisions: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    values = [
        value
        for decision in decisions
        if (value := _nonnegative_float(decision.get("objective_sacrifice"))) is not None
    ]
    positive = sum(value > 0.0 for value in values)
    observed = len(values)
    return {
        "observed": observed,
        "missing_or_invalid": len(decisions) - observed,
        "positive": positive,
        "positive_rate": (positive / observed if observed else None),
        "mean": (statistics.fmean(values) if values else None),
        "median": (statistics.median(values) if values else None),
        "minimum": (min(values) if values else None),
        "maximum": (max(values) if values else None),
    }


def _decision_rollup(decisions: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    reasons = Counter(str(decision.get("reason") or "unknown_reason") for decision in decisions)
    return {
        "rows": len(decisions),
        "reasons": _rate_table(reasons, len(decisions)),
        "composition": _composition_summary(decisions),
        "objective_sacrifice": _objective_sacrifice_summary(decisions),
    }


def _slate_size_bucket(decision: Mapping[str, Any]) -> str:
    n_games = _positive_int(decision.get("slate_game_count"))
    if n_games == 1:
        return "one_game"
    if n_games == 2:
        return "two_games"
    if n_games is not None and n_games >= 3:
        return "three_plus_games"
    return "unknown"


def _calendar_month(row: Mapping[str, Any]) -> str:
    raw = str(row.get("slate_date") or "")
    try:
        return dt.date.fromisoformat(raw[:10]).strftime("%Y-%m")
    except ValueError:
        return "unknown"


def _grouped_rollup(
    versioned: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]],
    *,
    key: str,
) -> dict[str, Any]:
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for row, decision in versioned:
        group = _slate_size_bucket(decision) if key == "slate_size" else _calendar_month(row)
        groups.setdefault(group, []).append(decision)
    return {group: _decision_rollup(groups[group]) for group in sorted(groups)}


def _coverage(rows: Sequence[Mapping[str, Any]]) -> dict[str, int | float]:
    counts = Counter(_placement_status(row) for row in rows)
    total = len(rows)
    exact = counts["exact"]
    censored = counts["censored"]
    unknown = counts["unknown"]
    return {
        "total": total,
        "exact": exact,
        "censored": censored,
        "unknown": unknown,
        "measured_coverage_rate": ((exact + censored) / total if total else 0.0),
    }


def summarize_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Summarize durable decision and placement coverage with explicit denominators."""

    versioned: list[tuple[Mapping[str, Any], dict[str, Any]]] = []
    instrumentation_counts: Counter[str] = Counter()
    for row in rows:
        state, decision = _decision_from_row(row)
        instrumentation_counts[state] += 1
        if state == "versioned" and decision is not None:
            versioned.append((row, decision))

    version_counts: Counter[str] = Counter()
    metadata_counts: Counter[str] = Counter()

    for _, decision in versioned:
        version = str(decision["policy_version"]).strip()
        metadata_quality = str(decision.get("metadata_quality") or "unknown")
        version_counts[version] += 1
        metadata_counts[metadata_quality] += 1

    versioned_count = len(versioned)
    versioned_rows = [row for row, _ in versioned]
    versioned_decisions = [decision for _, decision in versioned]
    overall_rollup = _decision_rollup(versioned_decisions)
    return {
        "schema_version": 1,
        "scope": {
            "freeze_selection": "latest_frozen_lineup_per_slate",
            "placement_selection": "latest_placement_per_slate",
            "placement_lineage": "slate_date_only_unverified",
            "interpretation": "coverage_only_not_policy_performance",
        },
        "rows": {
            "total": len(rows),
            "versioned": versioned_count,
            "legacy_uninstrumented": instrumentation_counts["legacy_uninstrumented"],
            "malformed_or_unversioned": instrumentation_counts["malformed_or_unversioned"],
        },
        "decisions": {
            "policy_versions": _rate_table(version_counts, versioned_count),
            "reasons": overall_rollup["reasons"],
            "metadata_quality": _rate_table(metadata_counts, versioned_count),
            "composition": overall_rollup["composition"],
            "objective_sacrifice": overall_rollup["objective_sacrifice"],
            "rollups": {
                "slate_size": _grouped_rollup(versioned, key="slate_size"),
                "calendar_month": _grouped_rollup(versioned, key="calendar_month"),
            },
        },
        "placement_coverage": {
            "all_selected_freezes": _coverage(rows),
            "versioned_stack_decisions": _coverage(versioned_rows),
        },
    }


def fetch_rows(engine: Any) -> list[dict[str, Any]]:
    """Read the analytics frame from one verified safe transaction."""

    connection = engine.connect().execution_options(isolation_level="REPEATABLE READ")
    try:
        with connection.begin():
            connection.execute(text("SET TRANSACTION READ ONLY"))
            read_only = str(
                connection.execute(text("SHOW transaction_read_only")).scalar_one()
            ).lower()
            isolation = str(
                connection.execute(text("SHOW transaction_isolation")).scalar_one()
            ).lower()
            if read_only != "on" or isolation != "repeatable read":
                raise RuntimeError("database transaction safety verification failed")
            result = connection.execute(ANALYTICS_QUERY)
            return [dict(row._mapping) for row in result]
    finally:
        connection.close()


def _render_text(summary: Mapping[str, Any]) -> str:
    rows = summary["rows"]
    decisions = summary["decisions"]
    composition = decisions["composition"]
    sacrifice = decisions["objective_sacrifice"]
    coverage = summary["placement_coverage"]
    lines = [
        "Stacking decision analytics",
        "Scope: latest frozen lineup and latest placement per slate",
        (
            "Rows: "
            f"{rows['total']} total, {rows['versioned']} versioned, "
            f"{rows['legacy_uninstrumented']} legacy/uninstrumented, "
            f"{rows['malformed_or_unversioned']} malformed/unversioned"
        ),
        (
            "Composition: "
            f"{composition['preferred']} preferred "
            f"({composition['preferred_rate']:.1%}), "
            f"{composition['concentrated']} concentrated "
            f"({composition['concentrated_rate']:.1%}), "
            f"{composition['unknown']} unknown; "
            f"determinate denominator={composition['determinate_denominator']}"
        ),
        "Decision reasons:",
    ]
    reasons = decisions["reasons"]
    if reasons:
        lines.extend(
            f"  {reason}: {values['count']} ({values['rate']:.1%} of versioned)"
            for reason, values in reasons.items()
        )
    else:
        lines.append("  none")
    lines.append(
        "Objective sacrifice: "
        f"{sacrifice['observed']} observed, {sacrifice['missing_or_invalid']} missing/invalid, "
        f"mean={sacrifice['mean']}, median={sacrifice['median']}"
    )
    lines.append("Prospective decision rollups:")
    for dimension, groups in decisions["rollups"].items():
        lines.append(f"  {dimension}:")
        for group, values in groups.items():
            group_composition = values["composition"]
            group_sacrifice = values["objective_sacrifice"]
            lines.append(
                f"    {group}: rows={values['rows']}, "
                f"preferred={group_composition['preferred']}, "
                f"concentrated={group_composition['concentrated']}, "
                f"unknown={group_composition['unknown']}, "
                f"mean_sacrifice={group_sacrifice['mean']}"
            )
    lines.append("Placement measurement coverage, not performance:")
    for label, values in coverage.items():
        lines.append(
            f"  {label}: {values['exact']} exact, {values['censored']} censored, "
            f"{values['unknown']} unknown, total={values['total']}"
        )
    lines.append(
        "Placement lineage is slate-date-only and unverified; unknown and censored rows "
        "are not counted as losses."
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    public_url = os.environ.get("DATABASE_PUBLIC_URL", "").strip()
    internal_url = os.environ.get("DATABASE_URL", "").strip()
    if not public_url and not internal_url:
        print("ERROR: set DATABASE_PUBLIC_URL or DATABASE_URL", file=sys.stderr)
        return 2
    url = _clean_url(public_url or internal_url)
    if public_url:
        try:
            _require_verified_tls(url)
        except ValueError:
            print(
                "ERROR: DATABASE_PUBLIC_URL must use sslmode=verify-ca or verify-full",
                file=sys.stderr,
            )
            return 2

    engine = None
    try:
        engine = create_engine(
            _sqlalchemy_url(url),
            connect_args={
                "connect_timeout": 20,
                "options": TRANSACTION_OPTIONS,
                "application_name": "wnba_stacking_analytics",
            },
        )
        rows = fetch_rows(engine)
        summary = summarize_rows(rows)
    except Exception:
        print("ERROR: stacking analytics query failed; details redacted", file=sys.stderr)
        return 1
    finally:
        if engine is not None:
            engine.dispose()

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(_render_text(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
