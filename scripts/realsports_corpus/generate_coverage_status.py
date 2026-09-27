#!/usr/bin/env python3
"""Offline coverage_manifest dry-run from durable-store fixtures (#526).

Builds a temporary kind-first corpus layout, projects checked-in
``fixtures/durable_stores`` into every required family, soft-merges
``coverage_manifest.json``, and prints a COMPLETE vs MISSING handoff report.

Never calls Real Sports. Never starts Ollama. Never mints credentials.

Usage::

    python scripts/realsports_corpus/generate_coverage_status.py \\
      --out-dir /tmp/rs-corpus-offline-status

    # Write snapshot under fixtures (for PR handoff):
    python scripts/realsports_corpus/generate_coverage_status.py --write-fixture-snapshot
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from realsports_corpus.coverage_manifest import (
    CoverageManifest,
    OllamaForbiddenError,
    assert_ollama_helper_forbidden,
    build_empty_manifest,
    coverage_manifest_path,
    is_historical_capture_complete,
    ollama_helper_allowed,
    write_coverage_manifest,
)
from realsports_corpus.export_stubs import (
    ExportResult,
    apply_export_results_to_manifest,
    export_nfl_corpus_c_contest,
    export_nfl_corpus_g_game,
    export_wnba_backup_csvs,
    scaffold_all_stub_families,
    write_family_stubs,
)
from realsports_corpus.layout import (
    REQUIRED_VARIABLE_FAMILIES,
    SPORTS,
    SlateKey,
    ensure_kind_roots,
)

PACKAGE = Path(__file__).resolve().parent
DURABLE = PACKAGE / "fixtures" / "durable_stores"
FIXTURE_SNAPSHOT = PACKAGE / "fixtures" / "offline_status"

# Operator handoff matrix after #532 / #533 / #534 / #537 / #538 / #539.
# "export_path" = monorepo code can project durable data into corpus layout.
# "sibling_payload" = cheeksmagunda/sports-realsports-corpus has real bytes.
HANDOFF_MATRIX: list[dict[str, str]] = [
    {
        "surface": "HV boards (total_value_leaderboards)",
        "wnba": "COMPLETE export path (#532/#539); MISSING sibling publish (needs CORPUS_REPO_TOKEN)",
        "nfl": "COMPLETE Corpus C offline export (#534); MISSING volume→sibling append",
        "nba": "MISSING ingest (fail-closed stub #532)",
        "nhl": "PARTIAL HV train path (#542); MISSING RS contest corpus export",
    },
    {
        "surface": "Corpus G (game boxes / players / feed)",
        "wnba": "MISSING RS Corpus-G-style store (game_logs partial elsewhere)",
        "nfl": "COMPLETE on Railway volume (~3k files); MISSING kind-first sibling publish",
        "nba": "MISSING",
        "nhl": "PARTIAL official NHL history; MISSING RS boxes in sibling",
    },
    {
        "surface": "Corpus C (contest archive)",
        "wnba": "n/a (Postgres slate_labels / contest_leaderboards)",
        "nfl": "COMPLETE offline HV+draftStats+matchups export (#534); MISSING sibling hydrate",
        "nba": "MISSING",
        "nhl": "MISSING",
    },
    {
        "surface": "Matchups / game-stats append",
        "wnba": "COMPLETE script path (#537); MISSING full-history sibling fill",
        "nfl": "COMPLETE Corpus G + #537 append; MISSING sibling soft-merge",
        "nba": "COMPLETE fail-closed append stub (#537); MISSING ingest",
        "nhl": "COMPLETE append stub (#537); MISSING RS matchup history in sibling",
    },
    {
        "surface": "draftStats all sections",
        "wnba": "COMPLETE dump CLI (#538) + Postgres export (#539); MISSING sibling publish",
        "nfl": "COMPLETE via Corpus C export (#534); MISSING sibling publish",
        "nba": "MISSING",
        "nhl": "MISSING durable (audit-only historically)",
    },
]


def _family_rollup(manifest: CoverageManifest) -> dict[str, dict[str, str]]:
    sports = manifest.payload.get("sports") or {}
    out: dict[str, dict[str, str]] = {}
    for sport in SPORTS:
        block = sports.get(sport) or {}
        families = block.get("families") or {}
        out[sport] = {
            family: str((families.get(family) or {}).get("status") or "unknown")
            for family in REQUIRED_VARIABLE_FAMILIES
        }
    return out


def run_offline_fixture_export(
    corpus_root: Path,
) -> tuple[CoverageManifest, list[ExportResult]]:
    """Project durable-store fixtures into corpus_root and return merged manifest."""

    ensure_kind_roots(corpus_root)
    results: list[ExportResult] = []
    manifest = build_empty_manifest()

    wnba_key = SlateKey(sport="wnba", year=2025, slate_date="2025-07-01")
    wnba_results = export_wnba_backup_csvs(
        corpus_root=corpus_root,
        key=wnba_key,
        backup_dir=DURABLE / "wnba_backup",
    )
    # Families without a backup CSV source stay explicit stubs for this slate.
    covered = {r.family for r in wnba_results}
    missing = tuple(f for f in REQUIRED_VARIABLE_FAMILIES if f not in covered)
    if missing:
        wnba_results.extend(
            write_family_stubs(
                corpus_root,
                wnba_key,
                missing,
                reason="wnba backup fixture has no durable source for this family",
            )
        )
    results.extend(wnba_results)
    manifest = apply_export_results_to_manifest(
        manifest,
        sport="wnba",
        results=wnba_results,
        year=wnba_key.year,
        slate_date=wnba_key.slate_date,
    )

    nfl_key = SlateKey(sport="nfl", year=2025, slate_date="2025-09-07")
    nfl_results = export_nfl_corpus_g_game(
        corpus_root=corpus_root,
        key=nfl_key,
        game_dir=DURABLE / "nfl_corpus_g" / "game_1",
    ) + export_nfl_corpus_c_contest(
        corpus_root=corpus_root,
        key=nfl_key,
        contest_dir=DURABLE / "nfl_corpus_c" / "contest_1",
    )
    covered_nfl = {r.family for r in nfl_results}
    missing_nfl = tuple(f for f in REQUIRED_VARIABLE_FAMILIES if f not in covered_nfl)
    if missing_nfl:
        nfl_results.extend(
            write_family_stubs(
                corpus_root,
                nfl_key,
                missing_nfl,
                reason="nfl durable fixtures leave this family uncovered",
            )
        )
    results.extend(nfl_results)
    manifest = apply_export_results_to_manifest(
        manifest,
        sport="nfl",
        results=nfl_results,
        year=nfl_key.year,
        slate_date=nfl_key.slate_date,
    )

    for sport, date in (("nba", "2025-10-01"), ("nhl", "2025-10-01")):
        key = SlateKey(sport=sport, year=2025, slate_date=date)  # type: ignore[arg-type]
        stub_results = scaffold_all_stub_families(corpus_root, key)
        results.extend(stub_results)
        manifest = apply_export_results_to_manifest(
            manifest,
            sport=sport,
            results=stub_results,
            year=key.year,
            slate_date=key.slate_date,
        )

    write_coverage_manifest(coverage_manifest_path(corpus_root), manifest)
    return manifest, results


def build_status_report(manifest: CoverageManifest) -> dict[str, Any]:
    """Machine-readable handoff report (no secrets)."""

    rollup = _family_rollup(manifest)
    complete = is_historical_capture_complete(manifest)
    ollama_gate = "ALLOWED (historical_capture_complete)" if complete else "FORBIDDEN"
    if complete:
        assert_ollama_helper_forbidden(manifest)
    else:
        try:
            assert_ollama_helper_forbidden(manifest)
        except OllamaForbiddenError:
            pass
        else:
            raise RuntimeError("ollama gate failed to forbid incomplete manifest")

    present_cells = 0
    total_cells = 0
    for sport in SPORTS:
        for family in REQUIRED_VARIABLE_FAMILIES:
            total_cells += 1
            if rollup[sport][family] == "present":
                present_cells += 1

    return {
        "schema_version": 1,
        "issue": 526,
        "mode": "offline_fixture_dry_run",
        "ollama": False,
        "historical_capture_complete": complete,
        "ollama_codespace_helper_allowed": ollama_helper_allowed(manifest),
        "ollama_gate": ollama_gate,
        "fixture_present_family_cells": present_cells,
        "fixture_total_family_cells": total_cells,
        "family_status_rollup": rollup,
        "handoff_matrix": HANDOFF_MATRIX,
        "operator_unlock_checklist": [
            "Do NOT install or wire Ollama until historical_capture_complete is true.",
            "Provision CORPUS_REPO_TOKEN (contents:write on cheeksmagunda/sports-realsports-corpus); agents must not mint.",
            "Confirm REALSPORTS_STORAGE_STATE_B64GZ is injected into Codespace process env (sha256[:8] only).",
            "Publish WNBA Postgres export (#539) + NFL Corpus C/G exports (#534/#537) into sibling via realsports-corpus-append workflow_dispatch confirm_append=true.",
            "Fill NBA RS ingest (today fail-closed) and NHL RS contest/HV durable export beyond official history.",
            "Soft-merge coverage_manifest.json until every sport×family is present with artifact_count>=1.",
            "Re-read sibling coverage_manifest.json; only then set/allow Ollama Codespace helper.",
        ],
        "sibling_corpus_live_note": (
            "As of dry-run generation: sibling repo holds kind dirs + empty "
            "coverage_manifest (all unknown) plus one synthetic NFL HV proof slate "
            "under total_value_leaderboards/nfl/2026/slate_2026-01-01/. "
            "historical_capture_complete remains false."
        ),
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# coverage_manifest offline status (#526)",
        "",
        f"- Mode: `{report['mode']}` (no Ollama, no Real Sports network)",
        f"- `historical_capture_complete`: **{report['historical_capture_complete']}**",
        f"- Ollama Codespace helper: **{report['ollama_gate']}**",
        (
            f"- Fixture family cells present: "
            f"{report['fixture_present_family_cells']}/"
            f"{report['fixture_total_family_cells']}"
        ),
        "",
        "## Sibling corpus (live)",
        "",
        report["sibling_corpus_live_note"],
        "",
        "## COMPLETE vs MISSING (post #532/#534/#537/#538/#539/#533)",
        "",
        "| Surface | WNBA | NFL | NBA | NHL |",
        "|---|---|---|---|---|",
    ]
    for row in report["handoff_matrix"]:
        lines.append(
            f"| {row['surface']} | {row['wnba']} | {row['nfl']} | "
            f"{row['nba']} | {row['nhl']} |"
        )
    lines.extend(
        [
            "",
            "## Fixture dry-run family rollup",
            "",
            "| Sport | " + " | ".join(REQUIRED_VARIABLE_FAMILIES) + " |",
            "|---|" + "|".join(["---"] * len(REQUIRED_VARIABLE_FAMILIES)) + "|",
        ]
    )
    rollup = report["family_status_rollup"]
    for sport in SPORTS:
        cells = " | ".join(rollup[sport][f] for f in REQUIRED_VARIABLE_FAMILIES)
        lines.append(f"| {sport} | {cells} |")
    lines.extend(["", "## Operator Ollama unlock checklist", ""])
    for i, step in enumerate(report["operator_unlock_checklist"], start=1):
        lines.append(f"{i}. {step}")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Write coverage_manifest.json + status report here",
    )
    parser.add_argument(
        "--write-fixture-snapshot",
        action="store_true",
        help=f"Also write snapshot under {FIXTURE_SNAPSHOT}",
    )
    parser.add_argument(
        "--json-stdout",
        action="store_true",
        help="Print status report JSON to stdout",
    )
    args = parser.parse_args(argv)

    out_dir = (args.out_dir or Path("/tmp/rs-corpus-offline-status")).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest, _results = run_offline_fixture_export(out_dir)
    report = build_status_report(manifest)
    md = render_markdown(report)

    (out_dir / "coverage_status.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "coverage_status.md").write_text(md, encoding="utf-8")

    if args.write_fixture_snapshot:
        FIXTURE_SNAPSHOT.mkdir(parents=True, exist_ok=True)
        write_coverage_manifest(
            FIXTURE_SNAPSHOT / "coverage_manifest.json",
            manifest,
        )
        (FIXTURE_SNAPSHOT / "coverage_status.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (FIXTURE_SNAPSHOT / "coverage_status.md").write_text(md, encoding="utf-8")
        print(f"wrote fixture snapshot -> {FIXTURE_SNAPSHOT}")

    print(md)
    if args.json_stdout:
        print(json.dumps(report, indent=2, sort_keys=True))
    print(
        f"wrote {out_dir / 'coverage_manifest.json'} "
        f"(complete={report['historical_capture_complete']}, "
        f"ollama={report['ollama_gate']})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
