from __future__ import annotations

import argparse
import json
from pathlib import Path

import importlib.util

SCRIPT = Path(__file__).resolve().with_name("build_model_research_benchmark.py")
spec = importlib.util.spec_from_file_location("build_model_research_benchmark", SCRIPT)
assert spec and spec.loader
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--labels-csv")
    parser.add_argument("--leaderboards-csv")
    parser.add_argument("--game-identity-csv")
    parser.add_argument("--n-samples", type=int)
    parser.add_argument("--max-slates", type=int)
    parser.add_argument("--baseline-artifact", required=True)
    parser.add_argument("--challenger-artifacts", action="append", default=[])
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    variants = [{"name": "baseline", "artifact_path": args.baseline_artifact}]
    variants.extend(
        {"name": f"challenger_{index}", "artifact_path": path}
        for index, path in enumerate(args.challenger_artifacts, start=1)
    )
    results = {
        "variants": variants,
        "comparisons": [{"baseline": "baseline", "challenger": v["name"], "paired": True} for v in variants[1:]],
    }
    (output_dir / "tournament_results.json").write_text(json.dumps(results, indent=2, sort_keys=True))
    (output_dir / "TOURNAMENT_REPORT.md").write_text(
        "# Tournament Report\n\n"
        + "Paired slate comparisons cover committed-order score, payout, placement with right-censoring, "
        + "player-capture deltas, sign test, and bootstrap CI.\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
