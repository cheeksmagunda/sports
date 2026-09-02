"""Job 1 persistence: enrichment UPSERTs and slate_meta timing writes.

Extracted from job1.py. Owns the SQL statements and the atomic
slate-promotion / slate_meta helpers. Callers must run ``pool_sanity``
before promoting a capture, so a partial upstream response never mixes
fresh timestamps with stale players.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Mapping

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
SLATE_META_TIP_READ = text("SELECT first_tip_utc FROM slate_meta WHERE slate_date = :slate_date")


def _decode_features(raw: object) -> dict:
    if raw is None:
        return {}
    if isinstance(raw, str):
        decoded = json.loads(raw)
        if not isinstance(decoded, dict):
            raise ValueError("job1_enrichment features_json must decode to an object")
        return decoded
    if isinstance(raw, Mapping):
        return dict(raw)
    raise ValueError("job1_enrichment features_json must be an object")


def _as_utc(value: object) -> dt.datetime | None:
    if isinstance(value, dt.datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=dt.UTC)
        return value.astimezone(dt.UTC)
    return parse_game_time(str(value or ""))


def _replace_enrichment(
    conn,
    slate_date: str,
    rows: list[dict],
    *,
    captured_at: dt.datetime | None = None,
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
    capture_time = captured_at or dt.datetime.now(dt.UTC)
    first_tip = _as_utc(
        conn.execute(SLATE_META_TIP_READ, {"slate_date": slate_date}).scalar_one_or_none()
    )
    slate_has_tipped = first_tip is not None and first_tip <= capture_time
    previous = {
        int(player_id): (str(opponent or ""), _decode_features(features_json))
        for player_id, opponent, features_json in conn.execute(
            JOB1_IDENTITY_READ, {"slate_date": slate_date}
        )
    }
    rows_to_persist: list[dict] = []
    for row in rows:
        prior = previous.get(int(row["player_id"]))
        if prior is None:
            rows_to_persist.append(row)
            continue
        prior_opponent, prior_features = prior
        prior_start = parse_game_time(str(prior_features.get("game_start_utc") or ""))
        player_has_tipped = prior_start is not None and prior_start <= capture_time
        if not player_has_tipped and not slate_has_tipped:
            rows_to_persist.append(row)
            continue

        updated = dict(row)
        updated_features = _decode_features(updated["features_json"])
        for key in ("game_id", "game_start_utc"):
            if prior_features.get(key):
                updated_features[key] = prior_features[key]
        if prior_opponent:
            updated["opponent"] = prior_opponent
        updated["features_json"] = json.dumps(updated_features)
        rows_to_persist.append(updated)

    conn.execute(JOB1_DELETE_SLATE, {"slate_date": slate_date})
    for row in rows_to_persist:
        conn.execute(JOB1_UPSERT, row)
    return len(rows_to_persist)


SLATE_META_UPSERT = text(
    """
    INSERT INTO slate_meta (
        slate_date, first_tip_utc, contest_lock_utc, source, payload_json, updated_at
    ) VALUES (
        :slate_date, :first_tip_utc, :contest_lock_utc, :source,
        CAST(:payload_json AS JSONB), now()
    )
    ON CONFLICT (slate_date) DO UPDATE SET
        first_tip_utc = CASE
            WHEN slate_meta.first_tip_utc IS NOT NULL
                AND slate_meta.first_tip_utc <= now()
            THEN slate_meta.first_tip_utc
            ELSE EXCLUDED.first_tip_utc
        END,
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
