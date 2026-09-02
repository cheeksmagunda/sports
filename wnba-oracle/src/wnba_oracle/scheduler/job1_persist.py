"""Job 1 persistence: enrichment UPSERTs and slate_meta timing writes.

Extracted from job1.py. Owns the SQL statements and the atomic
slate-promotion / slate_meta helpers. Callers must run ``pool_sanity``
before promoting a capture, so a partial upstream response never mixes
fresh timestamps with stale players.
"""

from __future__ import annotations

import datetime as dt
import json

from sqlalchemy import text

from wnba_oracle.common.logging import get_logger
from wnba_oracle.db.engine import get_engine

log = get_logger("oracle.job1")

JOB1_UPSERT = text(
    """
    INSERT INTO job1_enrichment (
        slate_date, player_id, real_sports_player_id, name, team, opponent,
        position, card_boost, features_json, captured_at
    ) VALUES (
        :slate_date, :player_id, :real_sports_player_id, :name, :team, :opponent,
        :position, :card_boost, :features_json, now()
    )
    ON CONFLICT (slate_date, player_id) DO UPDATE SET
        real_sports_player_id = EXCLUDED.real_sports_player_id,
        name = EXCLUDED.name,
        team = EXCLUDED.team,
        opponent = EXCLUDED.opponent,
        position = EXCLUDED.position,
        card_boost = EXCLUDED.card_boost,
        features_json = EXCLUDED.features_json,
        captured_at = now();
    """
)

JOB1_DELETE_SLATE = text("DELETE FROM job1_enrichment WHERE slate_date = :slate_date")
JOB1_IDENTITY_READ = text(
    """
    SELECT player_id, opponent, features_json
    FROM job1_enrichment
    WHERE slate_date = :slate_date
    """
)
def _feature_mapping(raw: object) -> dict:
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def _preserve_tipped_identity(
    rows: list[dict],
    existing: list[tuple[object, object, object]],
    *,
    now_utc: dt.datetime,
) -> list[dict]:
    """Keep prior matchup identity after its authoritative game has started."""
    existing_by_player = {
        int(str(player_id)): (opponent, features) for player_id, opponent, features in existing
    }
    preserved: list[dict] = []
    for row in rows:
        updated = dict(row)
        prior = existing_by_player.get(int(row["player_id"]))
        if prior is None:
            preserved.append(updated)
            continue
        old_opponent, old_features_raw = prior
        old_features = _feature_mapping(old_features_raw)
        game_start = parse_game_time(str(old_features.get("game_start_utc") or ""))
        if game_start is None or game_start > now_utc:
            preserved.append(updated)
            continue
        new_features = _feature_mapping(row.get("features_json"))
        for key in ("game_id", "game_start_utc"):
            if old_features.get(key):
                new_features[key] = old_features[key]
        updated["opponent"] = old_opponent
        updated["features_json"] = json.dumps(new_features)
        preserved.append(updated)
    return preserved


def _replace_enrichment(
    conn,
    slate_date: str,
    rows: list[dict],
    *,
    now_utc: dt.datetime | None = None,
) -> int:
    """Atomically promote one complete, validated slate capture.

    The transaction first removes the prior slate snapshot and then writes the
    new rows. Callers must run ``pool_sanity`` before invoking this helper, so a
    partial upstream response never mixes fresh timestamps with stale players.

    Once a player's stored game has tipped, its opponent and provider game
    identity belong to that slate. A later pool can contain the player's next
    fixture, so retain the established identity while refreshing non-identity
    signals.
    """
    current_time = now_utc or dt.datetime.now(dt.UTC)
    existing = conn.execute(JOB1_IDENTITY_READ, {"slate_date": slate_date}).fetchall()
    rows_to_write = _preserve_tipped_identity(rows, existing, now_utc=current_time)
    conn.execute(JOB1_DELETE_SLATE, {"slate_date": slate_date})
    for row in rows_to_write:
        conn.execute(JOB1_UPSERT, row)
    return len(rows_to_write)


SLATE_META_UPSERT = text(
    """
    INSERT INTO slate_meta (
        slate_date, first_tip_utc, contest_lock_utc, source, payload_json, updated_at
    ) VALUES (
        :slate_date, :first_tip_utc, :contest_lock_utc, :source,
        CAST(:payload_json AS JSONB), now()
    )
    ON CONFLICT (slate_date) DO UPDATE SET
        first_tip_utc = EXCLUDED.first_tip_utc,
        contest_lock_utc = EXCLUDED.contest_lock_utc,
        source = EXCLUDED.source,
        payload_json = EXCLUDED.payload_json,
        updated_at = now();
    """
)


def parse_game_time(raw: str) -> dt.datetime | None:
    """Parse a Real Sports game `dateTime` ("2026-05-27T23:00:00.000Z")
    into an aware UTC datetime. None on anything unparseable."""
    if not raw:
        return None
    try:
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    return parsed.astimezone(dt.UTC)


def _persist_slate_meta(slate_date: str, game_times: list[str]) -> None:
    """UPSERT the slate's timing facts (D83).

    first_tip_utc is the earliest game time, the contest-lock proxy.
    contest_lock_utc stays NULL until the platform exposes a real lock
    timestamp (probe 2026-06-10: the contest payload only carries a live
    `isLocked` boolean). A row with NULL first_tip_utc still gets written
    so the gate can tell "job1 looked and found nothing" from "job1 never
    ran" when debugging.
    """
    parsed = sorted(t for t in (parse_game_time(g) for g in game_times) if t is not None)
    first_tip = parsed[0] if parsed else None
    eng = get_engine()
    with eng.begin() as conn:
        conn.execute(
            SLATE_META_UPSERT,
            {
                "slate_date": slate_date,
                "first_tip_utc": first_tip,
                "contest_lock_utc": None,
                "source": "realsports_home_next",
                "payload_json": json.dumps({"game_times": game_times}),
            },
        )
    log.info(
        "job1_slate_meta",
        slate_date=slate_date,
        first_tip_utc=first_tip.isoformat() if first_tip else None,
        n_games=len(game_times),
    )


LITE_READ = text("SELECT id, name, team FROM job1_enrichment WHERE slate_date = :sd")
LITE_PATCH = text(
    "UPDATE job1_enrichment "
    "SET features_json = features_json || CAST(:patch AS jsonb) "
    "WHERE id = :id"
)

GAME_START_READ = text(
    "SELECT id, real_sports_player_id FROM job1_enrichment WHERE slate_date = :sd"
)
