"""Tests for Corpus G summarize + persist boundary."""

from __future__ import annotations

import json
from pathlib import Path

from nfl_oracle.ingest.corpus_g import CorpusGStore, summarize_payloads


def test_summarize_payloads_counts(
    sample_stats: dict, sample_players: dict, sample_feed: dict
) -> None:
    coverage = summarize_payloads(stats=sample_stats, players=sample_players, feed=sample_feed)
    assert coverage.n_player_box_scores == 5
    assert coverage.n_value_nonnull >= 1
    assert coverage.n_players == 3
    assert coverage.n_plays == 5
    assert coverage.game_season == 2002
    assert coverage.game_day == "2002-09-08"


def test_store_persists_redacted_endpoint(tmp_path: Path, sample_stats: dict) -> None:
    store = CorpusGStore(root=tmp_path)
    art = store.persist_endpoint(
        game_id=126323,
        season=2002,
        endpoint="stats",
        payload=sample_stats,
        source_url="https://web.realapp.com/games/126323/sport/nfl/stats",
    )
    raw = json.loads(art.path.read_text(encoding="utf-8"))
    assert "userId" not in raw
    assert "user" not in raw
    assert art.wrote is True
    assert len(art.provenance.content_sha256) == 64
