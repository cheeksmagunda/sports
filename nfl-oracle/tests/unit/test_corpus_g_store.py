from __future__ import annotations

import json
from pathlib import Path

from nfl_oracle.ingest.corpus_g import CorpusGStore, summarize_payloads

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "corpus_g"


def test_summarize_fixture_counts() -> None:
    stats = json.loads((FIXTURES / "stats.json").read_text())
    players = json.loads((FIXTURES / "players.json").read_text())
    feed = json.loads((FIXTURES / "feed_all.json").read_text())
    summary = summarize_payloads(stats=stats, players=players, feed=feed)
    assert summary.n_player_box_scores == 2
    assert summary.n_value_nonnull == 1
    assert summary.n_players == 1
    assert summary.n_plays == 2
    assert summary.game_season == 2002
    assert summary.game_day == "2002-09-08"


def test_store_persists_redacted_and_is_idempotent(tmp_path) -> None:
    store = CorpusGStore(root=tmp_path / "nfl-oracle")
    stats = json.loads((FIXTURES / "stats.json").read_text())
    first = store.persist_endpoint(
        game_id=126323,
        season=2002,
        endpoint="stats",
        payload=stats,
        source_url="https://web.realapp.com/games/126323/sport/nfl/stats",
    )
    second = store.persist_endpoint(
        game_id=126323,
        season=2002,
        endpoint="stats",
        payload=stats,
        source_url="https://web.realapp.com/games/126323/sport/nfl/stats",
    )
    assert first.wrote is True
    assert second.wrote is False
    saved = json.loads(first.path.read_text(encoding="utf-8"))
    assert "userId" not in json.dumps(saved)
    assert "token" not in saved
    prov = json.loads(first.provenance_path.read_text(encoding="utf-8"))
    assert prov["content_sha256"] == first.provenance.content_sha256
    assert prov["endpoint"] == "stats"
