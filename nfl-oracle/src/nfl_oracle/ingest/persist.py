"""Idempotent redacted payload persistence helper for Corpus G."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nfl_oracle.common.paths import resolve_project_root
from nfl_oracle.ingest.redact import assert_no_identity_leak, redact_corpus_payload


def corpus_g_root() -> Path:
    root = resolve_project_root(__file__)
    path = root / "data" / "raw" / "corpus_g"
    path.mkdir(parents=True, exist_ok=True)
    return path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def persist_corpus_g_payload(
    *,
    season: int,
    game_id: int,
    endpoint: str,
    payload: Any,
    day: str | None = None,
) -> dict[str, Any]:
    """Redact, hash, and write a Corpus G JSON payload. Idempotent on sha256."""

    redacted = redact_corpus_payload(payload)
    assert_no_identity_leak(redacted)
    raw = json.dumps(redacted, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = sha256_bytes(raw)
    season_dir = corpus_g_root() / f"season_{season}" / f"game_{game_id}"
    season_dir.mkdir(parents=True, exist_ok=True)
    out_path = season_dir / f"{endpoint}_{digest[:16]}.json"
    meta = {
        "season": season,
        "game_id": game_id,
        "day": day,
        "endpoint": endpoint,
        "content_sha256": digest,
        "captured_at": datetime.now(UTC).isoformat(),
        "path": str(out_path.relative_to(resolve_project_root(__file__))),
        "bytes": len(raw),
    }
    if out_path.exists():
        meta["deduped"] = True
        return meta
    out_path.write_bytes(raw)
    meta_path = season_dir / f"{endpoint}_{digest[:16]}.meta.json"
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    meta["deduped"] = False
    return meta
