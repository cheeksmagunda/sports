"""Export NFL game_stats + matchups from durable Corpus G (zero Real calls).

Reads an existing Corpus G tree (``data/raw/corpus_g/{season}/{game_id}/``)
or the offline fixtures under ``nfl-oracle/tests/fixtures/corpus_g/`` and
appends redacted artifacts into the sibling corpus layout (#526)::

    nfl/{season}/game_{id}/game_stats.json
    nfl/{season}/game_{id}/matchups.json
    nfl/{season}/game_{id}/feed.json   (when feed.json present)

Usage::

    uv run --frozen --package nfl-oracle python scripts/corpus/export_nfl_from_corpus_g.py \\
      --corpus-root /tmp/sports-realsports-corpus \\
      --corpus-g-root nfl-oracle/tests/fixtures/corpus_g --season 2024 --game-id 1
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from oracle_core.realsports_corpus import append_artifact, slate_or_game_key


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else None


def _matchups_from_stats(stats: dict[str, Any], *, game_id: int, season: str) -> dict[str, Any]:
    """Minimal matchup extraction for FeatureSpec wiring (#523).

    Corpus G ``gameBoxScore`` / box rows supply home/away scores; schedule
    joins elsewhere fill ``opponent_team`` / ``home_away``. This artifact is
    the durable Real Sports side of that join.
    """

    box = stats.get("gameBoxScore") if isinstance(stats.get("gameBoxScore"), dict) else {}
    players = list(stats.get("playerBoxScores") or [])
    n_value = sum(
        1
        for row in players
        if isinstance(row, dict) and row.get("value") is not None and str(row.get("value")).strip()
    )
    return {
        "schema_version": 1,
        "sport": "nfl",
        "season": season,
        "game_id": game_id,
        "label": "total_value_leaderboard",
        "home_score": box.get("homeScore"),
        "away_score": box.get("awayScore"),
        "n_player_box_scores": len(players),
        "n_value_nonnull": n_value,
        # FeatureSpec / own-model map (#523): these fields feed matchup + prior
        # groups (home_away, opponent_team, opp_def_value_allowed_prior) once
        # schedule identity is joined in nfl_oracle.features.
        "own_model_refs": {
            "issue": 523,
            "feature_groups": ["matchup", "prior", "pace"],
            "fields": {
                "home_score": "post-game context only (train label side)",
                "away_score": "post-game context only (train label side)",
                "playerBoxScores[].value": "Real value label / valuelaw target",
                "playerBoxScores[].playerId": "identity join",
            },
        },
        "source": "corpus_g.stats",
        "scraped_at": _utc_now(),
    }


def _export_game(
    *,
    corpus_root: Path,
    season: str,
    game_id: int,
    stats: dict[str, Any] | None,
    feed: dict[str, Any] | None,
    source_tag: str,
) -> list[dict[str, Any]]:
    key = slate_or_game_key(game_id=game_id)
    out: list[dict[str, Any]] = []
    if stats is not None:
        # Strip obvious identity leaks if present; fixtures may include them.
        safe_stats = {
            k: v
            for k, v in stats.items()
            if k not in {"token", "userId", "user"}
        }
        if isinstance(safe_stats.get("playerBoxScores"), list):
            cleaned = []
            for row in safe_stats["playerBoxScores"]:
                if not isinstance(row, dict):
                    continue
                cleaned.append(
                    {
                        kk: vv
                        for kk, vv in row.items()
                        if kk not in {"userId", "user", "token"}
                    }
                )
            safe_stats["playerBoxScores"] = cleaned
        out.append(
            append_artifact(
                corpus_root,
                sport="nfl",
                season=season,
                slate_or_game_id=key,
                artifact="game_stats",
                payload={
                    "schema_version": 1,
                    "sport": "nfl",
                    "season": season,
                    "game_id": game_id,
                    "source": source_tag,
                    "scraped_at": _utc_now(),
                    "stats": safe_stats,
                },
                source=source_tag,
            )
        )
        out.append(
            append_artifact(
                corpus_root,
                sport="nfl",
                season=season,
                slate_or_game_id=key,
                artifact="matchups",
                payload=_matchups_from_stats(stats, game_id=game_id, season=season),
                source=source_tag,
            )
        )
    if feed is not None:
        out.append(
            append_artifact(
                corpus_root,
                sport="nfl",
                season=season,
                slate_or_game_id=key,
                artifact="feed",
                payload={
                    "schema_version": 1,
                    "sport": "nfl",
                    "season": season,
                    "game_id": game_id,
                    "source": source_tag,
                    "scraped_at": _utc_now(),
                    "feed": feed,
                },
                source=source_tag,
            )
        )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument(
        "--corpus-g-root",
        type=Path,
        default=Path("nfl-oracle/tests/fixtures/corpus_g"),
        help="Corpus G tree or fixture directory (default: offline fixtures)",
    )
    parser.add_argument("--season", type=str, default="fixture")
    parser.add_argument("--game-id", type=int, default=0)
    args = parser.parse_args(argv)

    root = args.corpus_g_root
    if not root.exists():
        print(f"export_nfl_from_corpus_g: missing root {root}", file=sys.stderr)
        return 1

    # Fixture layout: flat stats.json / feed_all.json (no season dirs).
    flat_stats = _load_json(root / "stats.json")
    flat_feed = _load_json(root / "feed_all.json") or _load_json(root / "feed.json")
    if flat_stats is not None and not any(root.glob("[0-9]*")):
        game_id = args.game_id or 0
        summaries = _export_game(
            corpus_root=args.corpus_root,
            season=args.season,
            game_id=game_id,
            stats=flat_stats,
            feed=flat_feed,
            source_tag=f"corpus_g_fixture:{root.name}",
        )
        for s in summaries:
            print(
                "export_nfl_from_corpus_g: ok "
                f"artifact={s['artifact']} path={s['path']} wrote={s['wrote']}"
            )
        return 0 if summaries else 1

    # Production layout: {season}/{game_id}/stats.json
    season_dirs = sorted(p for p in root.iterdir() if p.is_dir() and p.name.isdigit())
    if args.season != "fixture":
        season_dirs = [root / args.season] if (root / args.season).is_dir() else []
    wrote = 0
    for season_dir in season_dirs:
        season = season_dir.name
        game_dirs = sorted(p for p in season_dir.iterdir() if p.is_dir() and p.name.isdigit())
        if args.game_id:
            game_dirs = [season_dir / str(args.game_id)]
        for game_dir in game_dirs:
            if not game_dir.is_dir():
                continue
            game_id = int(game_dir.name)
            stats = _load_json(game_dir / "stats.json")
            feed = _load_json(game_dir / "feed.json")
            if stats is None and feed is None:
                continue
            for s in _export_game(
                corpus_root=args.corpus_root,
                season=season,
                game_id=game_id,
                stats=stats,
                feed=feed,
                source_tag="corpus_g_volume_or_disk",
            ):
                print(
                    "export_nfl_from_corpus_g: ok "
                    f"artifact={s['artifact']} path={s['path']} wrote={s['wrote']}"
                )
                wrote += 1
    print(f"export_nfl_from_corpus_g: done artifacts={wrote}")
    return 0 if wrote else 1


if __name__ == "__main__":
    raise SystemExit(main())
