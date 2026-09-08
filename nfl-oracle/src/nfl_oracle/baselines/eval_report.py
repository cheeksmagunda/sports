"""Offline walk-forward evaluation report (baselines vs feature_ridge).

Observation only: fixture- or Corpus-G-driven. Never authenticates, never
enters contests, and never mutates dry-run/submit gates.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nfl_oracle.baselines.priors import BaselineKind
from nfl_oracle.baselines.walk_forward import WalkForwardReport, evaluate_walk_forward
from nfl_oracle.common.paths import resolve_project_root
from nfl_oracle.labels.schema import ValueLabel

# Full comparison set: classical priors + optional leakage-safe ridge.
COMPARISON_METHODS: tuple[BaselineKind, ...] = (
    "global_mean",
    "position_mean",
    "position_median",
    "player_mean",
    "feature_ridge",
)

SAMPLE_STEM = "walk_forward_fixture_sample"
LATEST_STEM = "walk_forward_latest"


@dataclass(frozen=True)
class MethodSummary:
    kind: BaselineKind
    n: int
    mae: float | None
    rmse: float | None
    bias: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "n": self.n,
            "mae": self.mae,
            "rmse": self.rmse,
            "bias": self.bias,
        }


@dataclass(frozen=True)
class WalkForwardEvalReport:
    """JSON-serializable comparison of baselines vs feature_ridge."""

    report: WalkForwardReport
    methods: tuple[BaselineKind, ...]
    ranking_by_mae: tuple[MethodSummary, ...]
    feature_ridge_vs_best_baseline: dict[str, Any]
    fixture_mode: bool
    root: str
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_only": True,
            "contest_entry": False,
            "dry_run": False,
            "mode": "walk_forward_eval",
            "fixture_mode": self.fixture_mode,
            "root": self.root,
            "methods": list(self.methods),
            "n_labels": self.report.n_labels,
            "seasons": list(self.report.seasons),
            "ranking_by_mae": [row.to_dict() for row in self.ranking_by_mae],
            "feature_ridge_vs_best_baseline": self.feature_ridge_vs_best_baseline,
            "notes": list(self.notes),
            "walk_forward": self.report.to_dict(),
        }


def default_fixture_root() -> Path:
    project = resolve_project_root(__file__)
    return project / "tests" / "fixtures" / "value_labels"


def default_artifacts_dir() -> Path:
    return resolve_project_root(__file__) / "artifacts"


def _summaries(report: WalkForwardReport) -> list[MethodSummary]:
    rows: list[MethodSummary] = []
    for kind, metrics in report.pooled.items():
        rows.append(
            MethodSummary(
                kind=kind,
                n=metrics.n,
                mae=metrics.mae,
                rmse=metrics.rmse,
                bias=metrics.bias,
            )
        )
    return rows


def _rank_by_mae(rows: Sequence[MethodSummary]) -> tuple[MethodSummary, ...]:
    def key(row: MethodSummary) -> tuple[int, float, str]:
        # Finite MAE first (lower better); missing MAE last.
        if row.mae is None:
            return (1, 0.0, row.kind)
        return (0, row.mae, row.kind)

    return tuple(sorted(rows, key=key))


def _ridge_vs_best_baseline(ranked: Sequence[MethodSummary]) -> dict[str, Any]:
    baselines = [row for row in ranked if row.kind != "feature_ridge"]
    ridge = next((row for row in ranked if row.kind == "feature_ridge"), None)
    best = next((row for row in baselines if row.mae is not None), None)
    if ridge is None:
        return {
            "feature_ridge_present": False,
            "best_baseline": best.kind if best else None,
            "delta_mae": None,
            "feature_ridge_better": None,
            "note": "feature_ridge not in methods set",
        }
    if best is None or ridge.mae is None or best.mae is None:
        return {
            "feature_ridge_present": True,
            "best_baseline": best.kind if best else None,
            "feature_ridge_mae": ridge.mae,
            "best_baseline_mae": best.mae if best else None,
            "delta_mae": None,
            "feature_ridge_better": None,
            "note": "insufficient pooled metrics for comparison",
        }
    delta = ridge.mae - best.mae
    return {
        "feature_ridge_present": True,
        "best_baseline": best.kind,
        "feature_ridge_mae": ridge.mae,
        "best_baseline_mae": best.mae,
        "delta_mae": delta,
        "feature_ridge_better": delta < 0.0,
        "note": (
            "Negative delta_mae means feature_ridge has lower pooled MAE "
            "than the best classical baseline (lower is better)."
        ),
    }


def build_eval_report(
    labels: Sequence[ValueLabel],
    *,
    methods: Sequence[BaselineKind] = COMPARISON_METHODS,
    root: Path | str | None = None,
    fixture_mode: bool = False,
    min_train_seasons: int = 1,
) -> WalkForwardEvalReport:
    """Run walk-forward and attach baseline-vs-ridge ranking metadata."""

    wf = evaluate_walk_forward(
        labels,
        baselines=methods,
        min_train_seasons=min_train_seasons,
    )
    ranked = _rank_by_mae(_summaries(wf))
    comparison = _ridge_vs_best_baseline(ranked)
    notes = list(wf.notes) + [
        "Eval report ranks pooled MAE across classical baselines and feature_ridge.",
        "Fixture-scale metrics are illustrative only; not contest decision value.",
        "Dry-run/submit gates are unchanged (contest_entry remains false).",
    ]
    return WalkForwardEvalReport(
        report=wf,
        methods=tuple(methods),
        ranking_by_mae=ranked,
        feature_ridge_vs_best_baseline=comparison,
        fixture_mode=fixture_mode,
        root=str(root) if root is not None else "",
        notes=tuple(notes),
    )


def render_markdown(eval_report: WalkForwardEvalReport) -> str:
    """Human-readable MD companion for the JSON artifact."""

    lines: list[str] = [
        "# Walk-forward evaluation report",
        "",
        "Observation only — no contest entry. Dry-run/submit gates unchanged.",
        "",
        f"- **root:** `{eval_report.root}`",
        f"- **fixture_mode:** `{eval_report.fixture_mode}`",
        f"- **labels:** {eval_report.report.n_labels}",
        f"- **seasons:** {list(eval_report.report.seasons)}",
        f"- **methods:** {list(eval_report.methods)}",
        "",
        "## Pooled ranking (lower MAE better)",
        "",
        "| rank | method | n | mae | rmse | bias |",
        "| ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for idx, row in enumerate(eval_report.ranking_by_mae, start=1):
        mae = "—" if row.mae is None else f"{row.mae:.6f}"
        rmse = "—" if row.rmse is None else f"{row.rmse:.6f}"
        bias = "—" if row.bias is None else f"{row.bias:.6f}"
        lines.append(f"| {idx} | `{row.kind}` | {row.n} | {mae} | {rmse} | {bias} |")

    cmp_ = eval_report.feature_ridge_vs_best_baseline
    lines.extend(
        [
            "",
            "## feature_ridge vs best baseline",
            "",
            f"- best_baseline: `{cmp_.get('best_baseline')}`",
            f"- feature_ridge_mae: `{cmp_.get('feature_ridge_mae')}`",
            f"- best_baseline_mae: `{cmp_.get('best_baseline_mae')}`",
            f"- delta_mae (ridge − best): `{cmp_.get('delta_mae')}`",
            f"- feature_ridge_better: `{cmp_.get('feature_ridge_better')}`",
            f"- note: {cmp_.get('note')}",
            "",
            "## Notes",
            "",
        ]
    )
    for note in eval_report.notes:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


@dataclass(frozen=True)
class WrittenReportPaths:
    json_path: Path
    md_path: Path
    latest_json: Path | None
    latest_md: Path | None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "json_path": str(self.json_path),
            "md_path": str(self.md_path),
            "latest_json": str(self.latest_json) if self.latest_json else None,
            "latest_md": str(self.latest_md) if self.latest_md else None,
        }


def write_eval_report(
    eval_report: WalkForwardEvalReport,
    out_dir: Path,
    *,
    stem: str = SAMPLE_STEM,
    also_latest: bool = True,
) -> WrittenReportPaths:
    """Write JSON + Markdown under ``out_dir`` (creates parents)."""

    out_dir.mkdir(parents=True, exist_ok=True)
    payload = eval_report.to_dict()
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(eval_report), encoding="utf-8")

    latest_json: Path | None = None
    latest_md: Path | None = None
    if also_latest and stem != LATEST_STEM:
        latest_json = out_dir / f"{LATEST_STEM}.json"
        latest_md = out_dir / f"{LATEST_STEM}.md"
        latest_json.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
        latest_md.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")

    return WrittenReportPaths(
        json_path=json_path,
        md_path=md_path,
        latest_json=latest_json,
        latest_md=latest_md,
    )
