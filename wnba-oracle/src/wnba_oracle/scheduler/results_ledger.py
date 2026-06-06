"""Append a finalized RESULTS.md entry for a slate, sourced from Postgres.

This is the no-screenshot path that keeps `RESULTS.md` current. Once a
contest finalizes (dayclose has ingested its leaderboard), this reads the
canonical store and writes a finalized slate entry:

  - our picks from `frozen_lineups` (the Job 2 freeze),
  - each pick's realized real_score from `slate_labels` (falling back to
    the per-player `value` carried in any captured leaderboard lineup),
  - the realized lineup total under the codebase scoring formula
    `(slot_mult + card_boost) * real_score` (see picker/optimize.py and
    scripts/backtest_optimizer.py),
  - where that total sits relative to the captured top-20 finishers.

What is NOT in the DB, and is therefore never fabricated here: our exact
rank and the full field size. `contest_leaderboards` stores only the
top-20 finishers per contest, so unless our entry placed top-20 the
ledger reports the realized total and the gap to the winner, and labels
rank/field-size as not-in-DB. Backfill those two numbers from a
screenshot if you want them.

Persistence note: on the Railway cron container the repo is ephemeral, so
a write here is lost unless `WNBA_RESULTS_LEDGER` points at a persisted /
committed path. The intended use is an operator/local run (or a future
GitHub Action) that regenerates the entry and commits it. dayclose only
calls this when `WNBA_RESULTS_LEDGER` is set, so the default Railway fire
is a clean no-op rather than a confusing ephemeral write. See DECISIONS D66.

CLI:
    oracle-results                       # finalize yesterday's slate (UTC)
    oracle-results --slate-date 2026-05-28
    oracle-results --dry-run             # print the entry, do not write
    oracle-results --force               # append even if the slate exists
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import Connection, text

from wnba_oracle.common.logging import configure_logging, get_logger
from wnba_oracle.common.settings import get_settings

log = get_logger("oracle.results")

# RESULTS.md lives at the repo root (three parents up from this module).
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LEDGER = REPO_ROOT / "RESULTS.md"
# New finalized entries are inserted directly below this sentinel, so the
# ledger stays newest-first without re-parsing prose.
AUTO_MARKER = "<!-- AUTO-APPEND-BELOW -->"


# --------------------------------------------------------------------------
# Pure model + rendering (no DB; unit-testable in isolation)
# --------------------------------------------------------------------------
@dataclass
class PlayerLine:
    player_id: int
    name: str
    team: str
    card_boost: float
    slot_mult: float
    real_score: float | None  # None => no realized label (DNP / not captured)

    @property
    def points(self) -> float:
        """Realized contribution: (slot_mult + card_boost) * real_score."""
        if self.real_score is None:
            return 0.0
        return (self.slot_mult + self.card_boost) * self.real_score

    @property
    def played(self) -> bool:
        return self.real_score is not None and self.real_score != 0.0


@dataclass
class SlateResult:
    slate_date: str
    model_sha: str
    payout_regime: str
    entry_recommendation: str
    expected_payout: float | None
    players: list[PlayerLine]
    leaderboard_scores: list[float] = field(default_factory=list)

    @property
    def total(self) -> float:
        return sum(p.points for p in self.players)

    @property
    def winner_score(self) -> float | None:
        return max(self.leaderboard_scores) if self.leaderboard_scores else None


def build_player_lines(
    lineup_json: dict, real_score_by_pid: dict[int, float | None]
) -> list[PlayerLine]:
    """Zip the frozen lineup's slot order against realized real_scores."""
    player_ids = [int(p) for p in lineup_json.get("player_ids", [])]
    slot_multipliers = [float(s) for s in lineup_json.get("slot_multipliers", [])]
    per_player = {
        int(pp["player_id"]): pp for pp in lineup_json.get("per_player", [])
    }
    lines: list[PlayerLine] = []
    for slot_idx, pid in enumerate(player_ids):
        pp = per_player.get(pid, {})
        slot_mult = slot_multipliers[slot_idx] if slot_idx < len(slot_multipliers) else 0.0
        lines.append(
            PlayerLine(
                player_id=pid,
                name=str(pp.get("display_name", f"Player {pid}")),
                team=str(pp.get("team", "")),
                card_boost=float(pp.get("card_boost", 0.0)),
                slot_mult=slot_mult,
                real_score=real_score_by_pid.get(pid),
            )
        )
    return lines


def position_summary(total: float, leaderboard_scores: list[float]) -> str:
    """Honest placement read against the captured top-20 (never invents a
    rank or field size, neither of which the DB stores)."""
    if not leaderboard_scores:
        return (
            "No leaderboard captured for this slate yet, so placement is "
            "unknown. Re-run once dayclose ingests the contest."
        )
    scores = sorted(leaderboard_scores, reverse=True)
    n = len(scores)
    worst_captured = scores[-1]
    winner = scores[0]
    gap = winner - total
    if total >= worst_captured:
        rank = sum(1 for s in scores if s > total) + 1
        return (
            f"Realized total **{total:.2f}** would rank ~**{rank} of the "
            f"{n} captured top finishers** (winner {winner:.2f}, "
            f"gap {gap:+.2f}). Exact rank and field size are not stored in "
            f"the DB (top-20 only); backfill from a screenshot if wanted."
        )
    return (
        f"Realized total **{total:.2f}** is below the {n}th captured score "
        f"({worst_captured:.2f}), i.e. **outside the captured top-20** "
        f"(winner {winner:.2f}, gap {gap:+.2f}). Exact rank and field size "
        f"are not stored in the DB; backfill from a screenshot if wanted."
    )


def render_entry(result: SlateResult, serving_knobs: Mapping[str, object]) -> str:
    """Render the finalized markdown block for one slate."""
    lines = result.players
    n_played = sum(1 for p in lines if p.played)
    rows = []
    for slot_idx, p in enumerate(lines, start=1):
        rs = "DNP / no label" if not p.played else f"{p.real_score:.2f}"
        pts = "—" if not p.played else f"{p.points:.2f}"
        eff = p.slot_mult + p.card_boost
        rows.append(
            f"| {slot_idx} | {p.name} | {p.team or '—'} | {p.slot_mult:.1f} | "
            f"{p.card_boost:.1f} | {eff:.1f} | {rs} | {pts} |"
        )
    table = "\n".join(rows)
    exp = (
        f"{result.expected_payout:.3f}"
        if result.expected_payout is not None
        else "—"
    )
    knob_str = ", ".join(f"`{k}={v}`" for k, v in serving_knobs.items())
    placement = position_summary(result.total, result.leaderboard_scores)
    return f"""## Slate {result.slate_date} — finalized

Status: final (auto-generated from Postgres on {dt.date.today().isoformat()}).
{placement}

Realized lineup total: **{result.total:.2f}** ({n_played} of {len(lines)} picks
posted a real_score). Scoring: `(slot_mult + card_boost) * real_score`.

| Slot | Player | Team | Slot mult | Boost | Eff mult | real_score | Points |
|------|--------|------|-----------|-------|----------|------------|--------|
{table}

### Fire-time / serving config
- `payout_regime={result.payout_regime}` (from the frozen row) `[verified]`
- `entry_recommendation={result.entry_recommendation}`, expected_payout {exp} `[verified]`
- `model_sha={result.model_sha}` `[verified]`
- serving config at report time: {knob_str} `[verified]`

### Read-through
- Winner {result.winner_score:.2f} vs our {result.total:.2f}. _(add the EV-vs-variance read here)_

"""


# --------------------------------------------------------------------------
# DB layer
# --------------------------------------------------------------------------
FROZEN_SELECT = text(
    """
    SELECT model_sha, payout_regime, entry_recommendation, expected_payout, lineup
    FROM frozen_lineups
    WHERE slate_date = :sd
    ORDER BY frozen_at DESC
    LIMIT 1
    """
)
LABELS_SELECT = text(
    "SELECT platform_player_id, real_score FROM slate_labels WHERE slate_date = :sd"
)
LEADERBOARD_SELECT = text(
    "SELECT score, lineup FROM contest_leaderboards WHERE slate_date = :sd ORDER BY rank ASC"
)


def _as_obj(raw: object) -> object:
    """JSONB columns arrive as dicts/lists with psycopg, but as str via some
    drivers. Normalize either way."""
    if isinstance(raw, (str, bytes)):
        return json.loads(raw)
    return raw


def load_slate_result(conn: Connection, slate_date: str) -> SlateResult | None:
    frozen = conn.execute(FROZEN_SELECT, {"sd": slate_date}).first()
    if frozen is None:
        return None
    lineup_json = _as_obj(frozen.lineup)
    if not isinstance(lineup_json, dict):
        raise ValueError(f"frozen lineup for {slate_date} is not a JSON object")

    # Realized real_score: slate_labels is canonical; fall back to the
    # per-player `value` carried verbatim in any captured leaderboard lineup.
    real_score_by_pid: dict[int, float | None] = {}
    for row in conn.execute(LABELS_SELECT, {"sd": slate_date}):
        real_score_by_pid[int(row.platform_player_id)] = (
            float(row.real_score) if row.real_score is not None else None
        )

    leaderboard_scores: list[float] = []
    for row in conn.execute(LEADERBOARD_SELECT, {"sd": slate_date}):
        leaderboard_scores.append(float(row.score))
        lineup = _as_obj(row.lineup)
        if not isinstance(lineup, list):
            continue
        for entry in lineup:
            if not isinstance(entry, dict):
                continue
            pid = entry.get("playerId")
            if pid is None or int(pid) in real_score_by_pid:
                continue
            val = entry.get("value")
            try:
                real_score_by_pid[int(pid)] = float(val) if val is not None else None
            except (TypeError, ValueError):
                real_score_by_pid[int(pid)] = None

    return SlateResult(
        slate_date=slate_date,
        model_sha=str(frozen.model_sha),
        payout_regime=str(frozen.payout_regime),
        entry_recommendation=str(frozen.entry_recommendation),
        expected_payout=(
            float(frozen.expected_payout)
            if frozen.expected_payout is not None
            else None
        ),
        players=build_player_lines(lineup_json, real_score_by_pid),
        leaderboard_scores=leaderboard_scores,
    )


# --------------------------------------------------------------------------
# Ledger I/O
# --------------------------------------------------------------------------
def slate_already_logged(ledger_text: str, slate_date: str) -> bool:
    return f"## Slate {slate_date}" in ledger_text


def insert_entry(ledger_text: str, entry: str) -> str:
    """Insert a rendered entry directly below the AUTO_MARKER (newest-first).
    Falls back to prepending before the first existing slate heading, then to
    appending, if the marker is absent."""
    if AUTO_MARKER in ledger_text:
        head, tail = ledger_text.split(AUTO_MARKER, 1)
        return f"{head}{AUTO_MARKER}\n\n{entry}{tail.lstrip()}"
    marker = "\n## Slate "
    idx = ledger_text.find(marker)
    if idx != -1:
        return f"{ledger_text[:idx + 1]}{entry}{ledger_text[idx + 1:]}"
    return ledger_text.rstrip() + "\n\n" + entry


def append_for_slate(
    slate_date: str,
    ledger_path: Path | None = None,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> int:
    """Load a slate result from Postgres and append it to the ledger.

    Returns a process exit code: 0 on success or benign no-op, 1 on a hard
    failure (no DATABASE_URL, malformed frozen row)."""
    settings = get_settings()
    if not settings.database_url:
        log.error("results_no_database_url", slate_date=slate_date)
        return 1

    ledger_path = ledger_path or DEFAULT_LEDGER
    from wnba_oracle.db.engine import get_engine

    with get_engine().connect() as conn:
        result = load_slate_result(conn, slate_date)
    if result is None:
        log.info("results_no_frozen_lineup", slate_date=slate_date)
        return 0

    serving_knobs = {
        "CONTRARIAN_ENABLED": settings.contrarian_enabled,
        "CONTRARIAN_STRENGTH": settings.contrarian_strength,
        "OPTIMIZER_MAX_PER_TEAM": settings.optimizer_max_per_team,
        "PAYOUT_REGIME": settings.payout_regime,
    }
    entry = render_entry(result, serving_knobs)

    if dry_run:
        sys.stdout.write(entry)
        return 0

    existing = ledger_path.read_text() if ledger_path.exists() else ""
    if slate_already_logged(existing, slate_date) and not force:
        log.info("results_slate_already_logged", slate_date=slate_date)
        return 0

    ledger_path.write_text(insert_entry(existing, entry))
    log.info(
        "results_entry_appended",
        slate_date=slate_date,
        realized_total=round(result.total, 2),
        path=str(ledger_path),
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Append a finalized RESULTS.md entry.")
    parser.add_argument(
        "--slate-date",
        default=(dt.date.today() - dt.timedelta(days=1)).isoformat(),
        help="Slate date (YYYY-MM-DD). Defaults to yesterday (UTC).",
    )
    parser.add_argument("--ledger", default=None, help="Path to RESULTS.md.")
    parser.add_argument(
        "--force", action="store_true", help="Append even if the slate is already logged."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print the entry; do not write."
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    ledger_path = Path(args.ledger) if args.ledger else None
    return append_for_slate(
        args.slate_date, ledger_path, force=args.force, dry_run=args.dry_run
    )


if __name__ == "__main__":
    sys.exit(main())
