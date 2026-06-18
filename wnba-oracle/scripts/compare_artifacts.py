"""Compare two PickerArtifact pickles by trained-model CONTENT (determinism gate).

LightGBM Booster pickles are not byte-stable even when the trained model is
identical, so the determinism gate compares the canonical model serialization
plus the EB baseline parameters instead of pickle SHAs (NEEDS_HUMAN #14 fix).

Usage:
    python scripts/compare_artifacts.py A.pkl B.pkl
Exit 0 if the trained content is identical, 1 if it diverges, 2 on bad args.
"""

from __future__ import annotations

import pickle
import sys

from wnba_oracle.train.pipeline import artifact_content_equal


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: compare_artifacts.py A.pkl B.pkl", file=sys.stderr)
        return 2
    with open(argv[1], "rb") as fh:
        a = pickle.load(fh)
    with open(argv[2], "rb") as fh:
        b = pickle.load(fh)
    equal, reason = artifact_content_equal(a, b)
    print(("PASS - " if equal else "FAIL - ") + reason)
    return 0 if equal else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
