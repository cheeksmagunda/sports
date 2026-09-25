from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from nhl_oracle.contract.discovery import discover_contract
from nhl_oracle.contract.gates import evaluate_nhl_audit
from nhl_oracle.contract.schema import ContestFormat, NhlAuditFixture
from nhl_oracle.ingest.provenance import NhlCorpusStore
from nhl_oracle.ingest.redact import assert_no_identity_leak, redact_corpus_payload

FIXTURES = Path(__file__).parent / "fixtures" / "realsports"


def test_gates_pass_on_redacted_fixture_corpus(tmp_path: Path) -> None:
    meta = json.loads((FIXTURES / "contest_meta.json").read_text(encoding="utf-8"))
    draftinfo = json.loads((FIXTURES / "contest_draftinfo.json").read_text(encoding="utf-8"))
    players = json.loads((FIXTURES / "game_players.json").read_text(encoding="utf-8"))

    redacted_meta = redact_corpus_payload(meta)
    redacted_draft = redact_corpus_payload(draftinfo)
    redacted_players = redact_corpus_payload(players)
    assert_no_identity_leak(redacted_meta)
    assert_no_identity_leak(redacted_draft)
    assert_no_identity_leak(redacted_players)

    store = NhlCorpusStore(tmp_path)
    captured_at = "2026-09-24T12:00:00Z"
    store.persist_endpoint(
        game_id=9001,
        season=2026,
        endpoint="contest",
        payload=redacted_meta,
        source_url="https://example.invalid/contest",
        captured_at=captured_at,
    )
    store.persist_endpoint(
        game_id=9001,
        season=2026,
        endpoint="draftinfo",
        payload=redacted_draft,
        source_url="https://example.invalid/draftinfo",
        captured_at=captured_at,
    )
    store.persist_endpoint(
        game_id=501,
        season=2026,
        endpoint="players",
        payload=redacted_players,
        source_url="https://example.invalid/players",
        captured_at=captured_at,
    )

    contract, evidence, candidates = discover_contract(
        meta=redacted_meta,
        draftinfo=redacted_draft,
        players_payloads=[redacted_players],
        contest_ids=(9001,),
        game_ids=(501,),
        games_scheduled=1,
        games_captured=1,
        captured_at=captured_at,
    )
    assert contract.format is ContestFormat.FIVE_CARD_ORDERED
    assert evidence.games_captured == 1
    assert evidence.players_resolved == 5
    fixture = NhlAuditFixture(
        contract=contract,
        candidates=candidates,
        expected_roster_size=contract.roster_size,
    )
    report = evaluate_nhl_audit(fixture, decision_at=datetime(2026, 9, 24, 13, 0, tzinfo=UTC))
    assert report.contest_entry is False
    assert report.all_gates_ok is True
