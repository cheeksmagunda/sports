"""Feature-pipeline provenance hash.

``feature_module_sha`` is pickled alongside the trained artifact so
reloading it can verify the feature-build source hasn't drifted since
training.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def feature_module_sha() -> str:
    """SHA over the feature-pipeline source. Pickled alongside the artifact
    so reloading verifies the build path hasn't drifted."""
    h = hashlib.blake2b(digest_size=16)
    for name in (
        "rolling.py",
        "spec.py",
        "game_features.py",
        "corpus.py",
        "serving_features.py",
        "serving_schema.py",
    ):
        p = Path(__file__).parent / name
        if p.exists():
            h.update(p.read_bytes())
    return h.hexdigest()
