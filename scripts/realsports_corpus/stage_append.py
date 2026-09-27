"""Stage an append into the Real Sports corpus checkout.

Soft-merges coverage_manifest.json and copies kind payloads under the
canonical kind-first layout. Does not talk to Real Sports (#526).
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_ROOT / "scripts"))

from realsports_corpus.coverage_manifest import (
    build_empty_manifest,
    coverage_manifest_path,
    load_coverage_manifest,
    record_family_status,
    write_coverage_manifest,
)
from realsports_corpus.layout import (
    REQUIRED_VARIABLE_FAMILIES,
    SPORTS,
    SlateKey,
    ensure_kind_roots,
    family_dir,
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_layout(corpus_root: Path) -> None:
    missing = [
        name for name in REQUIRED_VARIABLE_FAMILIES if not (corpus_root / name).is_dir()
    ]
    if missing:
        raise SystemExit(f"corpus layout missing kinds: {', '.join(missing)}")
    manifest_path = coverage_manifest_path(corpus_root)
    if not manifest_path.is_file():
        raise SystemExit(f"missing coverage_manifest.json at {manifest_path}")
    load_coverage_manifest(manifest_path)
    print("layout ok:", corpus_root)


def _stage_append(
    corpus_root: Path,
    source: Path,
    *,
    sport: str,
    year: str,
    slate_date: str,
    kind: str,
    label: str,
) -> None:
    if sport not in SPORTS:
        raise SystemExit(f"unknown sport {sport!r}; expected one of {SPORTS}")
    if kind not in REQUIRED_VARIABLE_FAMILIES:
        raise SystemExit(
            f"unknown kind {kind!r}; expected one of {REQUIRED_VARIABLE_FAMILIES}"
        )
    if not source.is_dir():
        raise SystemExit(f"source directory missing: {source}")

    key = SlateKey(sport=sport, year=int(year), slate_date=slate_date)  # type: ignore[arg-type]
    dest_dir = family_dir(corpus_root, key, kind)  # type: ignore[arg-type]
    dest_dir.mkdir(parents=True, exist_ok=True)

    copied: list[Path] = []
    # Top-level files only. Nested trees belong in their own kind staging
    # calls so one HV proof cannot accidentally swallow Corpus G samples.
    for path in sorted(source.iterdir()):
        if not path.is_file():
            continue
        target = dest_dir / path.name
        shutil.copy2(path, target)
        copied.append(target)

    if not copied:
        raise SystemExit(f"no files under source {source}")

    primary = dest_dir / "payload.json"
    sha_path = primary if primary.is_file() else copied[0]
    sha256 = _sha256_file(sha_path)

    manifest_path = coverage_manifest_path(corpus_root)
    if manifest_path.is_file():
        manifest = load_coverage_manifest(manifest_path)
    else:
        manifest = build_empty_manifest()
    manifest = record_family_status(
        manifest,
        sport=sport,  # type: ignore[arg-type]
        family=kind,  # type: ignore[arg-type]
        status="present",
        artifact_count=len(copied),
        note=label,
        year=int(year),
        slate_date=slate_date,
        sha256=sha256,
    )
    write_coverage_manifest(manifest_path, manifest)
    print(f"staged {len(copied)} file(s) -> {dest_dir}")
    print(f"coverage soft-merged for {sport}/{year}/{slate_date}/{kind}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=None)
    parser.add_argument("--sport", default="nfl", choices=list(SPORTS))
    parser.add_argument("--year", default="2026")
    parser.add_argument("--slate-date", default="2026-01-01")
    parser.add_argument(
        "--kind",
        default="total_value_leaderboards",
        choices=list(REQUIRED_VARIABLE_FAMILIES),
    )
    parser.add_argument("--label", default="append")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only verify corpus layout + coverage_manifest.json",
    )
    parser.add_argument(
        "--ensure-roots",
        action="store_true",
        help="Create missing kind directories before validate/stage",
    )
    args = parser.parse_args(argv)

    corpus_root = args.corpus_root.resolve()
    if args.ensure_roots:
        ensure_kind_roots(corpus_root)
        if not coverage_manifest_path(corpus_root).is_file():
            write_coverage_manifest(
                coverage_manifest_path(corpus_root), build_empty_manifest()
            )
    if args.validate_only:
        _validate_layout(corpus_root)
        return 0
    if args.source is None:
        raise SystemExit("--source is required unless --validate-only")
    _validate_layout(corpus_root)
    _stage_append(
        corpus_root,
        args.source.resolve(),
        sport=args.sport,
        year=args.year,
        slate_date=args.slate_date,
        kind=args.kind,
        label=args.label,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
