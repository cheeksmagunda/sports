"""Tests for season backfill cursor resume and Corpus G gap helpers."""

from __future__ import annotations

import json
from pathlib import Path

from nfl_oracle.ingest.backfill import (
    BackfillCursor,
    games_missing_players,
    load_cursor,
    load_season_game_ids,
    save_cursor,
    scan_corpus_gaps,
)
from nfl_oracle.ingest.backfill import (
    main as backfill_main,
)
from nfl_oracle.ingest.corpus_g import CorpusGStore


def test_cursor_round_trip(tmp_path: Path) -> None:
    store = CorpusGStore(root=tmp_path)
    cursor = BackfillCursor(
        season=2002,
        last_game_id=126323,
        completed_game_ids=[126323],
    )
    save_cursor(store, cursor)
    loaded = load_cursor(store)
    assert loaded.season == 2002
    assert loaded.last_game_id == 126323
    assert loaded.completed_game_ids == [126323]
    assert loaded.updated_at


def test_load_season_game_ids_explicit_and_catalog(tmp_path: Path) -> None:
    catalog = tmp_path / "season_game_ids.json"
    catalog.write_text(json.dumps({"2002": [126323]}), encoding="utf-8")
    assert load_season_game_ids(2002, catalog_path=catalog) == [126323]
    assert load_season_game_ids(2002, explicit=[9, 8]) == [9, 8]


def _write_game(store: CorpusGStore, season: int, game_id: int, *files: str) -> None:
    game_dir = store.game_dir(season, game_id)
    for name in files:
        (game_dir / name).write_text("{}", encoding="utf-8")


def test_scan_corpus_gaps_and_missing_players(tmp_path: Path) -> None:
    store = CorpusGStore(root=tmp_path)
    _write_game(store, 2024, 18790, "stats.json", "feed.json")
    _write_game(store, 2024, 18800, "stats.json", "feed.json", "players.json")
    _write_game(store, 2025, 19440, "stats.json", "feed.json", "players.json")

    rows = {row.season: row for row in scan_corpus_gaps(store)}
    assert rows["2024"].games == 2
    assert rows["2024"].complete == 1
    assert rows["2024"].missing_players == 1
    assert rows["2025"].complete == 1
    assert rows["2025"].missing_players == 0

    missing = games_missing_players(store, season=2024)
    assert missing == [(2024, 18790)]
    assert games_missing_players(store, season=2024, explicit=[18800]) == []


def test_report_gaps_cli_offline(tmp_path: Path, monkeypatch, capsys) -> None:
    store = CorpusGStore(root=tmp_path)
    _write_game(store, 2024, 18790, "stats.json", "feed.json")
    monkeypatch.chdir(tmp_path)
    # CorpusGStore() resolves project root from package location; point raw via cwd
    # is insufficient. Invoke scan helpers through CLI with store rooted at tmp
    # by monkeypatching the default constructor root.
    monkeypatch.setattr(
        "nfl_oracle.ingest.backfill.CorpusGStore",
        lambda root=None: CorpusGStore(root=tmp_path),
    )
    rc = backfill_main(["--report-gaps", "--season", "2024"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "season=2024" in out
    assert "missing_players=1" in out
