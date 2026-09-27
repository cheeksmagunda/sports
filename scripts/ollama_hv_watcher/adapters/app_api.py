"""Read-only adapter over each sport app's public API (#574).

The Ollama helper never decides the lineup. Each sport app fires its own
T-40 freeze and serves a frozen five-player lineup; this adapter only READS
those public endpoints (stdlib ``urllib``, bounded timeout and retry, no
credentials) so the helper can (a) derive the slate's watch window from the
app's own cutoff / freeze target and (b) copy the app's frozen five into a
PRE-GAME board for annotation.

Base URLs come from the environment only (no hardcoded hosts):

* ``SPORTS_OLLAMA_NFL_API_URL``  (nfl-oracle recommendations API)
* ``SPORTS_OLLAMA_WNBA_API_URL`` (wnba-oracle API)

Missing env raises ``LiveDataRequiredError``. Current URLs are recorded in
each app's ``STATUS.md``.

Response shapes (read from app code, confirmed by live GET on 2026-09-27):

NFL ``nfl-oracle/src/nfl_oracle/recommendations/app.py``
  ``GET /slate/{day}`` and ``GET /lineup/{day}`` return one snapshot:
  ``slate_date``, ``status`` (``waiting`` | ``frozen`` | ``locked`` | run
  status), ``stale``, ``games`` (``kickoff_at``, ``status`` per game; empty
  until frozen), ``run.details.cutoff_at`` / ``run.details.next_freeze``
  before freeze, and top-level ``cutoff_at`` / ``frozen_at`` / ``digest`` /
  ``sequence`` plus ``lineup.picks[]`` (``projected_value``, ``slot``,
  ``slot_multiplier``, ``card_boost``, ...) once frozen. ``lineup`` is
  ``null`` until the freeze fires.

WNBA ``wnba-oracle/src/wnba_oracle/api/slate.py`` and ``lineup.py``
  ``GET /slate/{day}`` returns ``first_tip_utc``, ``contest_lock_utc``,
  ``freeze_lead_minutes``, ``freeze_target_utc``, ``picks_paused`` (404
  until job1 captures tip times). ``GET /lineup/{day}`` returns
  ``frozen_at``, ``model_sha``, ``freeze_seq``, ``frozen_via`` and
  ``lineup.per_player[]`` in committed slot order plus
  ``lineup.slot_multipliers`` (404 until frozen).

No sport-app imports: shapes are parsed from JSON only.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from ollama_hv_watcher.boards import LIVE_BOARD_FILENAME
from ollama_hv_watcher.learn import atomic_write_json
from ollama_hv_watcher.live import LiveDataRequiredError
from ollama_hv_watcher.pick import APP_FROZEN_SECTION, FIVE_PLAYER_LINEUP_SIZE
from ollama_hv_watcher.windows import SlateWindow, parse_iso_utc

API_URL_ENV: dict[str, str] = {
    "nfl": "SPORTS_OLLAMA_NFL_API_URL",
    "wnba": "SPORTS_OLLAMA_WNBA_API_URL",
}
SUPPORTED_SPORTS = tuple(sorted(API_URL_ENV))

DEFAULT_TIMEOUT_S = 10.0
DEFAULT_ATTEMPTS = 3
DEFAULT_BACKOFF_S = 1.0
DEFAULT_DATA_ROOT = Path("data/ollama_hv")
USER_AGENT = "sports-ollama-hv-helper/1 (+#574 read-only)"

# NFL close rule, copied (not imported) from nfl-oracle
# ``src/nfl_oracle/calendar/week_close.py``: a game is treated as settled
# no earlier than kickoff + MIN_GAME_DURATION + FINALIZATION_BUFFER.
NFL_MIN_GAME_DURATION = timedelta(hours=3)
NFL_FINALIZATION_BUFFER = timedelta(hours=1)
# nfl-oracle freezes at cutoff - 40 minutes
# (``recommendations/pipeline.py`` / ``cli.py``); used only when the API
# does not expose ``next_freeze``.
NFL_FREEZE_LEAD_MINUTES = 40

# WNBA close rule (helper-owned): the WNBA API exposes only the first tip /
# contest lock, not the last tip, so the helper keeps watching for a fixed
# span after the lock. Generous by design: the close only bounds how long
# the helper stays alive and never touches the app's freeze or serving.
WNBA_CLOSE_AFTER_LOCK = timedelta(hours=6)

# A frozen NFL snapshot the app itself marks ``stale`` is refused.
NFL_FROZEN_STATUSES = frozenset({"frozen", "locked"})
FINAL_GAME_STATUSES = frozenset({"final", "finalized", "completed", "closed"})

UrlOpen = Callable[..., Any]
SleepFn = Callable[[float], None]


class AppApiUnavailableError(RuntimeError):
    """The app API could not be reached after bounded retries."""


@dataclass(frozen=True)
class AppResponse:
    status: int
    payload: Any
    url: str


def _check_sport(sport: str) -> str:
    key = str(sport).strip().lower()
    if key not in API_URL_ENV:
        raise LiveDataRequiredError(
            "sport",
            context=f"no app API adapter for sport={sport!r}; have={SUPPORTED_SPORTS}",
        )
    return key


def _check_day(day: str) -> str:
    try:
        return date.fromisoformat(str(day)).isoformat()
    except ValueError as exc:
        raise LiveDataRequiredError(
            "day", context=f"need YYYY-MM-DD got={day!r}"
        ) from exc


def base_url(sport: str, *, environ: Mapping[str, str] | None = None) -> str:
    """Return the sport app's API base URL from env or fail closed."""

    env = environ if environ is not None else os.environ
    key = _check_sport(sport)
    name = API_URL_ENV[key]
    raw = str(env.get(name, "")).strip()
    if not raw:
        raise LiveDataRequiredError(
            name,
            context=(
                f"set {name} to the {key} app API base URL (see the app STATUS.md)"
            ),
        )
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme not in ("https", "http") or not parsed.netloc:
        raise LiveDataRequiredError(name, context="must be an http(s) base URL")
    if parsed.username or parsed.password or parsed.query:
        raise LiveDataRequiredError(
            name, context="base URL must not carry credentials or a query"
        )
    return raw.rstrip("/")


def get_json(
    url: str,
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    attempts: int = DEFAULT_ATTEMPTS,
    backoff_s: float = DEFAULT_BACKOFF_S,
    sleep_fn: SleepFn = time.sleep,
) -> AppResponse:
    """GET JSON with bounded retries. 404 is returned, not retried."""

    attempts = max(1, int(attempts))
    last_error = ""
    for attempt in range(1, attempts + 1):
        req = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": USER_AGENT},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                status = int(getattr(resp, "status", 200) or 200)
                body = resp.read()
            return AppResponse(status=status, payload=json.loads(body), url=url)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return AppResponse(status=404, payload=None, url=url)
            last_error = f"http_{exc.code}"
            if exc.code < 500 and exc.code != 429:
                break
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = type(exc).__name__
        except ValueError:
            last_error = "invalid_json"
        if attempt < attempts:
            sleep_fn(backoff_s * attempt)
    raise AppApiUnavailableError(
        f"app_api_unavailable url={url} attempts={attempts} error={last_error}"
    )


def _fetch(
    sport: str,
    path: str,
    *,
    environ: Mapping[str, str] | None,
    sleep_fn: SleepFn,
    timeout_s: float,
) -> AppResponse:
    return get_json(
        f"{base_url(sport, environ=environ)}{path}",
        timeout_s=timeout_s,
        sleep_fn=sleep_fn,
    )


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _require_dict(resp: AppResponse, *, field: str) -> dict[str, Any]:
    if not isinstance(resp.payload, dict):
        raise LiveDataRequiredError(field, context=f"url={resp.url}; not_object")
    return resp.payload


def _require_slate_date(payload: dict[str, Any], day: str, *, url: str) -> None:
    got = str(payload.get("slate_date") or "")[:10]
    if got != day:
        raise LiveDataRequiredError(
            "slate_date",
            context=f"url={url}; expected={day} got={got!r}",
        )


def _ts(value: Any, field: str, *, url: str) -> datetime:
    if value in (None, ""):
        raise LiveDataRequiredError(field, context=f"url={url}")
    try:
        return parse_iso_utc(str(value))
    except ValueError as exc:
        raise LiveDataRequiredError(
            field, context=f"url={url}; unparseable={value!r}"
        ) from exc


def _obj(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


# --------------------------------------------------------------------- NFL


def _nfl_cutoff_and_freeze(
    payload: dict[str, Any], *, url: str
) -> tuple[datetime, datetime | None]:
    run = _obj(payload.get("run"))
    details = _obj(run.get("details"))
    cutoff_raw = payload.get("cutoff_at") or details.get("cutoff_at")
    cutoff = _ts(cutoff_raw, "cutoff_at", url=url)
    freeze_raw = payload.get("next_freeze") or details.get("next_freeze")
    freeze = _ts(freeze_raw, "next_freeze", url=url) if freeze_raw else None
    return cutoff, freeze


def _nfl_window(payload: dict[str, Any], day: str, *, url: str) -> SlateWindow:
    _require_slate_date(payload, day, url=url)
    run = _obj(payload.get("run"))
    if str(payload.get("status") or run.get("status") or "") == "no_slate":
        raise LiveDataRequiredError("slate", context=f"url={url}; app status no_slate")
    cutoff, freeze = _nfl_cutoff_and_freeze(payload, url=url)
    lead = NFL_FREEZE_LEAD_MINUTES
    if freeze is not None:
        lead = round((cutoff - freeze).total_seconds() / 60.0)
        if lead < 0:
            raise LiveDataRequiredError(
                "next_freeze", context=f"url={url}; freeze after cutoff"
            )
    kickoffs = [
        _ts(g.get("kickoff_at"), "games[].kickoff_at", url=url)
        for g in payload.get("games") or []
        if isinstance(g, dict)
    ]
    # Before the freeze the app exposes only ``cutoff_at`` (slate lock, the
    # first kickoff). The daemon re-reads the window every poll, so the close
    # extends to the real last kickoff as soon as the frozen snapshot lists
    # its games.
    last_kickoff = max([cutoff, *kickoffs])
    close = last_kickoff + NFL_MIN_GAME_DURATION + NFL_FINALIZATION_BUFFER
    return SlateWindow(
        sport="nfl",
        slate_id=day,
        freeze_or_kickoff_at=cutoff,
        close_at=close,
        lead_minutes=lead,
    )


def _nfl_board(payload: dict[str, Any], day: str, *, url: str) -> dict[str, Any] | None:
    _require_slate_date(payload, day, url=url)
    lineup = payload.get("lineup")
    if lineup is None:
        return None  # app has not frozen yet
    if not isinstance(lineup, dict):
        raise LiveDataRequiredError("lineup", context=f"url={url}; not_object")
    status = str(payload.get("status") or "")
    if status not in NFL_FROZEN_STATUSES:
        raise LiveDataRequiredError(
            "status", context=f"url={url}; lineup present but status={status!r}"
        )
    if payload.get("stale") is True:
        raise LiveDataRequiredError(
            "stale", context=f"url={url}; app marks frozen lineup stale; refuse"
        )
    picks = lineup.get("picks")
    if not isinstance(picks, list) or len(picks) != FIVE_PLAYER_LINEUP_SIZE:
        have = len(picks) if isinstance(picks, list) else None
        raise LiveDataRequiredError(
            "lineup.picks", context=f"url={url}; need exactly 5 got={have}"
        )
    frozen_at = _ts(payload.get("frozen_at"), "frozen_at", url=url)
    cutoff, _ = _nfl_cutoff_and_freeze(payload, url=url)
    players: list[dict[str, Any]] = []
    for index, pick in enumerate(picks):
        if not isinstance(pick, dict):
            raise LiveDataRequiredError(f"lineup.picks[{index}]", context=url)
        if pick.get("projected_value") is None:
            raise LiveDataRequiredError(
                f"lineup.picks[{index}].projected_value", context=url
            )
        row: dict[str, Any] = {
            "player_id": pick.get("player_id"),
            "name": pick.get("name"),
            "team": pick.get("team"),
            "value": float(pick["projected_value"]),
            "value_field": "projected_value",
            "slot": pick.get("slot", index + 1),
        }
        for key in (
            "position",
            "opponent",
            "game_id",
            "slot_multiplier",
            "card_boost",
            "projected_score",
            "ownership",
        ):
            if pick.get(key) is not None:
                row[key] = pick[key]
        players.append(row)
    game_statuses = {
        str(g.get("status") or "").lower()
        for g in payload.get("games") or []
        if isinstance(g, dict)
    }
    game_status = (
        "final" if game_statuses and game_statuses <= FINAL_GAME_STATUSES else "pregame"
    )
    return {
        "sport": "nfl",
        "slate_key": day,
        "label": "nfl_app_frozen_lineup",
        "section": APP_FROZEN_SECTION,
        "phase": "pregame",
        "game_status": game_status,
        "source": url,
        "frozen_at": _iso(frozen_at),
        "cutoff_at": _iso(cutoff),
        "app_status": status,
        "app_lineup": {
            k: payload.get(k)
            for k in ("digest", "sequence", "model_fingerprint")
            if payload.get(k) is not None
        }
        | {
            k: lineup.get(k)
            for k in ("objective", "total_value", "boost_regime")
            if lineup.get(k) is not None
        },
        "players": players,
    }


# -------------------------------------------------------------------- WNBA


def _wnba_window(payload: dict[str, Any], day: str, *, url: str) -> SlateWindow:
    _require_slate_date(payload, day, url=url)
    if payload.get("picks_paused") is True:
        raise LiveDataRequiredError(
            "picks_paused",
            context=f"url={url}; app picks paused resumes_on={payload.get('resumes_on')}",
        )
    lock_raw = payload.get("contest_lock_utc") or payload.get("first_tip_utc")
    lock = _ts(lock_raw, "contest_lock_utc|first_tip_utc", url=url)
    freeze = _ts(payload.get("freeze_target_utc"), "freeze_target_utc", url=url)
    lead = round((lock - freeze).total_seconds() / 60.0)
    if lead < 0:
        raise LiveDataRequiredError(
            "freeze_target_utc", context=f"url={url}; freeze after lock"
        )
    return SlateWindow(
        sport="wnba",
        slate_id=day,
        freeze_or_kickoff_at=lock,
        close_at=lock + WNBA_CLOSE_AFTER_LOCK,
        lead_minutes=lead,
    )


def _wnba_board(payload: dict[str, Any], day: str, *, url: str) -> dict[str, Any]:
    _require_slate_date(payload, day, url=url)
    lineup = payload.get("lineup")
    if not isinstance(lineup, dict):
        raise LiveDataRequiredError("lineup", context=f"url={url}; not_object")
    per_player = lineup.get("per_player")
    if not isinstance(per_player, list) or len(per_player) != FIVE_PLAYER_LINEUP_SIZE:
        have = len(per_player) if isinstance(per_player, list) else None
        raise LiveDataRequiredError(
            "lineup.per_player", context=f"url={url}; need exactly 5 got={have}"
        )
    ids = lineup.get("player_ids")
    if isinstance(ids, list) and [str(i) for i in ids] != [
        str(p.get("player_id")) for p in per_player if isinstance(p, dict)
    ]:
        raise LiveDataRequiredError(
            "lineup.player_ids", context=f"url={url}; order disagrees with per_player"
        )
    frozen_at = _ts(payload.get("frozen_at"), "frozen_at", url=url)
    multipliers = lineup.get("slot_multipliers")
    players: list[dict[str, Any]] = []
    for index, pick in enumerate(per_player):
        if not isinstance(pick, dict):
            raise LiveDataRequiredError(f"lineup.per_player[{index}]", context=url)
        # The WNBA API exposes no per-player projected value, so the helper
        # uses the model's median projection ``pred_real_score_p50``. It is a
        # PRE-GAME prediction, never an actual score.
        if pick.get("pred_real_score_p50") is None:
            raise LiveDataRequiredError(
                f"lineup.per_player[{index}].pred_real_score_p50", context=url
            )
        row: dict[str, Any] = {
            "player_id": pick.get("player_id"),
            "name": pick.get("display_name") or pick.get("name"),
            "team": pick.get("team"),
            "value": float(pick["pred_real_score_p50"]),
            "value_field": "pred_real_score_p50",
            "slot": index + 1,
        }
        if isinstance(multipliers, list) and index < len(multipliers):
            row["slot_multiplier"] = multipliers[index]
        for key in ("position", "opponent", "game_id", "card_boost", "archetype"):
            if pick.get(key) is not None:
                row[key] = pick[key]
        if pick.get("pred_real_score_p10") is not None:
            row["projection_p10"] = pick["pred_real_score_p10"]
        if pick.get("pred_real_score_p90") is not None:
            row["projection_p90"] = pick["pred_real_score_p90"]
        players.append(row)
    return {
        "sport": "wnba",
        "slate_key": day,
        "label": "wnba_app_frozen_lineup",
        "section": APP_FROZEN_SECTION,
        "phase": "pregame",
        "game_status": "pregame",
        "source": url,
        "frozen_at": _iso(frozen_at),
        "app_lineup": {
            k: payload.get(k)
            for k in ("model_sha", "freeze_seq", "frozen_via", "payout_regime")
            if payload.get(k) is not None
        }
        | {
            k: lineup.get(k) for k in ("lineup_score_p50",) if lineup.get(k) is not None
        },
        "players": players,
    }


# ------------------------------------------------------------------ public


def slate_window(
    sport: str,
    day: str,
    *,
    environ: Mapping[str, str] | None = None,
    sleep_fn: SleepFn = time.sleep,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> SlateWindow:
    """Watch window from the app's own cutoff / freeze target (fail closed)."""

    key = _check_sport(sport)
    day = _check_day(day)
    resp = _fetch(
        key, f"/slate/{day}", environ=environ, sleep_fn=sleep_fn, timeout_s=timeout_s
    )
    if resp.status == 404:
        raise LiveDataRequiredError(
            "slate_timing", context=f"url={resp.url}; app has no timing yet (404)"
        )
    payload = _require_dict(resp, field="slate")
    if key == "nfl":
        return _nfl_window(payload, day, url=resp.url)
    return _wnba_window(payload, day, url=resp.url)


def frozen_board(
    sport: str,
    day: str,
    *,
    environ: Mapping[str, str] | None = None,
    data_root: Path | None = DEFAULT_DATA_ROOT,
    sleep_fn: SleepFn = time.sleep,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> dict[str, Any] | None:
    """The app's frozen five as a PRE-GAME board, or None if not frozen yet.

    Fails closed (``LiveDataRequiredError``) when the app serves anything but
    exactly five picks, marks the freeze stale, or answers for another day.
    When ``data_root`` is set the board is written atomically to
    ``data_root/<sport>/<day>/hv_board.json``.
    """

    key = _check_sport(sport)
    day = _check_day(day)
    resp = _fetch(
        key, f"/lineup/{day}", environ=environ, sleep_fn=sleep_fn, timeout_s=timeout_s
    )
    if resp.status == 404:
        return None
    payload = _require_dict(resp, field="lineup")
    board = (
        _nfl_board(payload, day, url=resp.url)
        if key == "nfl"
        else _wnba_board(payload, day, url=resp.url)
    )
    if board is None:
        return None
    if data_root is not None:
        atomic_write_json(Path(data_root) / key / day / LIVE_BOARD_FILENAME, board)
    return board


def windows_payload(
    day: str,
    sports: list[str],
    *,
    environ: Mapping[str, str] | None = None,
    sleep_fn: SleepFn = time.sleep,
) -> dict[str, Any]:
    """Build a ``SPORTS_OLLAMA_WINDOWS_JSON`` payload from the app APIs.

    Per-sport failures are reported under ``errors``; never invented.
    """

    day = _check_day(day)
    slates: list[dict[str, Any]] = []
    errors: dict[str, str] = {}
    for sport in sports:
        try:
            window = slate_window(sport, day, environ=environ, sleep_fn=sleep_fn)
        except (LiveDataRequiredError, AppApiUnavailableError) as exc:
            errors[str(sport)] = str(exc)
            continue
        row = window.to_dict()
        row["source"] = "app_api"
        row["close_rule"] = (
            "last_kickoff+3h+1h(nfl-oracle week_close)"
            if window.sport == "nfl"
            else "contest_lock+6h(helper; app exposes first tip only)"
        )
        slates.append(row)
    return {
        "day": day,
        "generated_at": _iso(datetime.now(UTC)),
        "slates": slates,
        "errors": errors,
    }
