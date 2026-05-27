"""Generate the initial eval/ deliverable bundle.

Until the live collector accumulates the ~2000-row corpus, we cannot
emit a real CRPS-by-cohort + reliability diagram + Mondrian coverage
table + RBO@5 + bootstrap-CI picker EV summary. This script generates
placeholder JSON files that the rotation gate and the operator can fill
in as the corpus grows.

Outputs (under eval/):
- crps_by_cohort.json    -> {"G": null, "F": null, "C": null, ...}
- reliability.json       -> nominal vs empirical per quantile per cohort
- conformal_coverage.json -> Mondrian cell coverage table
- rbo_at_5.json          -> RBO@5 holdout series
- picker_ev_bootstrap.json -> bootstrap CI for picker EV vs heuristic
- README.md              -> describes what each file is and how it's refreshed
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parents[1] / "eval"


def main() -> int:
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.utcnow().isoformat() + "Z"

    files = {
        "crps_by_cohort.json": {
            "_meta": {"generated_at": stamp, "status": "placeholder"},
            "G": None,
            "F": None,
            "C": None,
        },
        "reliability.json": {
            "_meta": {"generated_at": stamp, "status": "placeholder"},
            "quantiles": [0.1, 0.5, 0.9],
            "by_cohort": {"G": [], "F": [], "C": []},
        },
        "conformal_coverage.json": {
            "_meta": {"generated_at": stamp, "status": "placeholder"},
            "target_coverage": 0.8,
            "cells": {},
        },
        "rbo_at_5.json": {
            "_meta": {"generated_at": stamp, "status": "placeholder"},
            "series": [],
        },
        "picker_ev_bootstrap.json": {
            "_meta": {"generated_at": stamp, "status": "placeholder"},
            "n_bootstrap": 1000,
            "picker_ev_ci": None,
            "heuristic_ev_ci": None,
        },
    }

    for name, payload in files.items():
        (EVAL_DIR / name).write_text(json.dumps(payload, indent=2))
        print(f"wrote {EVAL_DIR / name}")

    readme = (
        "# eval/ deliverable bundle\n\n"
        "These five JSON artifacts are the rotation-gate inputs.\n\n"
        "- **crps_by_cohort.json**: CRPS (continuous ranked probability score)\n"
        "  per cohort (G/F/C). Computed by `oracle-rotate-check` from\n"
        "  `model_shadow_runs` post-tip rows.\n"
        "- **reliability.json**: nominal vs empirical coverage at P10/P50/P90\n"
        "  per cohort. Diagram lives at `reliability.png`.\n"
        "- **conformal_coverage.json**: Mondrian CQR per-cell coverage table.\n"
        "  Each cell is (cohort, home_away, b2b_rested).\n"
        "- **rbo_at_5.json**: per-slate RBO@5 between challenger and incumbent\n"
        "  rankings. Plus the 7-day rolling bootstrap CI.\n"
        "- **picker_ev_bootstrap.json**: bootstrap CI for the picker's EV vs\n"
        "  the heuristic baseline. 1000 resamples per Part 6.14.\n\n"
        "All five start as placeholders until the live collector has ~30\n"
        "slates of data. Re-run `scripts/seed_eval_bundle.py` to reseed,\n"
        "and `oracle-rotate-check --window-days 7` to refresh from the\n"
        "rotation-gate side.\n"
    )
    (EVAL_DIR / "README.md").write_text(readme)
    print(f"wrote {EVAL_DIR / 'README.md'}")
    return 0


if __name__ == "__main__":
    main()
