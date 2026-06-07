"""Job 2: predict + freeze near tip. Redis SET NX + Postgres UPSERT.

Once the lineup freezes, it never re-rolls intra-day. The Redis key
`wnba.frozen.{slate_date}` is SET with NX + TTL=24h; if it already exists
this Job 2 invocation is a no-op (idempotent). The Postgres frozen_lineups
table is UPSERTed on (slate_date, model_sha).

Pipeline:
1. Read Job 1 enrichment from job1_enrichment table.
2. Load the model artifact (if WNBA_ORACLE_MODEL_ARTIFACT_SHA set + file
   exists). Else use the transparent heuristic picker (low-data fallback).
3. Build sampling/field specs for the optimizer.
4. Load payout curve (from archive if available, else default for regime).
5. Run optimize_lineup.
6. Freeze.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sqlalchemy import text

from wnba_oracle.common.logging import configure_logging, get_logger
from wnba_oracle.common.settings import get_settings
from wnba_oracle.db.engine import get_engine, get_redis
from wnba_oracle.features.game_script_minutes import (
    GameScriptInput,
    GameScriptMinutesConfig,
    blowout_probability,
    redistribute_game_script_minutes,
)
from wnba_oracle.features.injury_cascade import CascadeInput, redistribute_minutes
from wnba_oracle.features.spec import cohort_for_position
from wnba_oracle.picker.field import FieldPlayerSpec
from wnba_oracle.picker.game_script import GameScriptConfig, game_script_multiplier
from wnba_oracle.picker.optimize import LineupRecommendation, OptimizeConfig, optimize_lineup
from wnba_oracle.picker.payout import default_curve_for_regime, load_curve_from_archive
from wnba_oracle.picker.popularity import (
    ContrarianConfig,
    apply_contrarian_adjustment,
    estimate_draft_popularity,
    slate_labels_to_popularity,
)
from wnba_oracle.picker.sample import PlayerSamplingSpec
from wnba_oracle.predict.availability import AvailabilityConfig, availability_probability
from wnba_oracle.predict.form import player_volatility
from wnba_oracle.predict.minutes import MinutesConfig, blended_real_score
from wnba_oracle.train.pipeline import PickerArtifact, load_artifact

log = get_logger("oracle.job2")

# Anchor definition for the Tier 1 lineup anchor floor (D57): a player we are
# confident logs real minutes tonight. Either an established rotation player
# (>= ANCHOR_MIN_GAMES recent games averaging >= ANCHOR_MIN_MINUTES) or a
# RotoWire-confirmed starter. Cold-start darts (no minutes history) are NOT
# anchors -- they are exactly the boost longshots that sank 2026-06-01.
ANCHOR_MIN_GAMES = 3
ANCHOR_MIN_MINUTES = 20.0


@dataclass(frozen=True)
class Job2Result:
    slate_date: str
    model_sha: str
    recommendation: LineupRecommendation | None
    frozen: bool
    reason: str


def _heuristic_real_score(card_boost: float) -> float:
    """Transparent fallback used when no model artifact is loaded.

    Calibrated 2026-05-27 against the 16-slate parquet corpus (D43):
    `real_score = 3.16 - 0.45 * card_boost` (linear fit, n=449
    player-slates from 2026-05-10 onward — the date the boost system
    rolled out). The slope is NEGATIVE because card_boost is a handicap
    the platform assigns to weaker baseline players to balance the
    multiplier contribution. A boost-3 player has lower expected
    real_score (1.8) than a boost-0 player (3.16); the boost mechanic
    compensates via the additive (slot + boost) effective multiplier.

    Floored at 0.5 because the picker uses pred_real_score as the
    log-scale mean for sampling, and a near-zero centre would explode
    the percentile band.
    """
    return max(0.5, 3.16 - 0.45 * card_boost)


REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_player_history() -> dict[int, float]:
    """Per-player mean real_score from slate_labels in Postgres.

    Used as a fallback prediction tier between the EB model and the generic
    heuristic. Players not yet in the EB model (trained before their 2026 data
    was backfilled) but with any corpus history get their actual observed mean
    rather than the boost-level heuristic. This matters most for boost-3
    players: the heuristic gives them 1.81, but a player like Milic whose only
    observed slate scored 0.51 should not be treated as average-for-boost-3.

    Returns an empty dict on any read/parse error so the caller degrades
    gracefully to the heuristic.
    """
    try:
        from wnba_oracle.db.reads import read_player_history

        return read_player_history()
    except Exception:
        return {}


def _load_model_artifact(sha: str) -> PickerArtifact | None:
    """Load the trained PickerArtifact whose SHA256 matches `sha`.

    Looks under `models/` for any `picker_*.pkl` whose sidecar
    `.sha256` file matches. Returns None on any failure (missing,
    SHA mismatch, unpickle error) — the caller falls back to the
    transparent heuristic.

    Empty `sha` short-circuits to None so deployments without the
    env var set behave exactly like the pre-D45 heuristic-only path.
    """
    if not sha:
        return None
    sha = sha.strip().lower()
    models_dir = REPO_ROOT / "models"
    if not models_dir.exists():
        log.warning("model_artifact_dir_missing", dir=str(models_dir))
        return None
    # `write_artifact` writes the sidecar at `picker_<commit>_<ts>.sha256`
    # (path.with_suffix(".sha256") REPLACES `.pkl`, it doesn't append).
    for sidecar in models_dir.glob("picker_*.sha256"):
        try:
            disk_sha = sidecar.read_text().strip().lower()
        except OSError:
            continue
        if disk_sha != sha:
            continue
        pkl_path = sidecar.with_suffix(".pkl")
        if not pkl_path.exists():
            log.warning("model_artifact_pkl_missing", path=str(pkl_path))
            return None
        try:
            art = load_artifact(pkl_path)
        except Exception as exc:
            log.exception("model_artifact_load_failed", path=str(pkl_path), error=str(exc))
            return None
        log.info(
            "model_artifact_loaded",
            path=str(pkl_path),
            sha=sha[:12],
            training_rows=art.training_rows,
            low_data_mode=art.low_data_mode,
            n_heads=len(art.heads),
            has_eb_baseline=art.eb_baseline is not None,
            n_eb_players=len(art.eb_baseline.player_alpha) if art.eb_baseline else 0,
        )
        return art
    log.warning("model_artifact_sha_not_found", sha=sha[:12])
    return None


def _eb_predict_one(art: PickerArtifact | None, player_id: int, position: str) -> float | None:
    """Single-player EB prediction with cohort + player-alpha lookup.

    Returns None if (a) no artifact, (b) no EB baseline in artifact, or
    (c) player_id wasn't seen in training. Caller falls back to the
    heuristic on None — this preserves graceful degradation for new
    players the model never saw. The `team_pace` term is dropped
    because job1_enrichment doesn't yet carry team pace.
    """
    if art is None or art.eb_baseline is None:
        return None
    eb = art.eb_baseline
    if int(player_id) not in eb.player_alpha:
        return None
    cohort = cohort_for_position(position)
    mu = eb.cohort_means.get(cohort, 0.0)
    alpha = eb.player_alpha[int(player_id)]
    pred = mu + alpha
    return max(0.5, float(pred))


def _load_enrichment(slate_date: str) -> list[dict]:
    eng = get_engine()
    q = text(
        "SELECT real_sports_player_id, name, team, opponent, position, "
        "card_boost, features_json "
        "FROM job1_enrichment WHERE slate_date = :sd"
    )
    with eng.connect() as conn:
        result = conn.execute(q, {"sd": slate_date})
        return [dict(row._mapping) for row in result]


def _features_dict(features_json: object) -> dict:
    """Coerce the features_json column into a dict. psycopg returns JSONB
    as parsed dicts; older test fixtures pass strings."""
    if not features_json:
        return {}
    if isinstance(features_json, str):
        import json as _json

        try:
            return _json.loads(features_json)
        except _json.JSONDecodeError:
            return {}
    return features_json if isinstance(features_json, dict) else {}


def _vegas_from_features(features_json: object) -> tuple[float, float]:
    """Extract (vegas_total, vegas_spread) from the features_json JSONB.
    Returns (0.0, 0.0) when absent so the game-script multiplier degrades
    to neutral."""
    f = _features_dict(features_json)
    return (
        float(f.get("vegas_total", 0.0) or 0.0),
        float(f.get("vegas_spread", 0.0) or 0.0),
    )


def _is_out_from_features(features_json: object) -> bool:
    """Drop signal: RotoWire confirmed OUT/IL/INJ/NA/INACTIVE. job1
    writes ``is_out`` as an int (0/1) into features_json after matching
    each Real Sports player to the RotoWire lineup index. Players with
    no RotoWire match (or with a non-OUT status like GTD/DTD/Q/P) keep
    is_out=0 and remain in the optimizer pool."""
    f = _features_dict(features_json)
    return bool(int(f.get("is_out", 0) or 0))


def _starter_multiplier(features_json: object, *, enabled: bool) -> float:
    """Real_score multiplier from the RotoWire confirmed-starter flag (D52).

    card_boost is a lagging rolling-rating handicap, so it cannot know
    tonight's starting five. RotoWire's same-day confirmation is the one
    pre-game signal additive to boost. We only act on CONFIRMED rows
    (rotowire_confirmed=1); an unconfirmed/unmatched player gets 1.0 (no
    info) so we never punish a player RotoWire simply did not list.

    Magnitudes are modest on purpose -- boost already captures most of a
    player's role, so this is a nudge for same-day starts/sits, not a
    wholesale re-rating. confirmed starter -> 1.10, confirmed non-starter
    -> 0.82.
    """
    if not enabled:
        return 1.0
    f = _features_dict(features_json)
    if not int(f.get("rotowire_confirmed", 0) or 0):
        return 1.0
    return 1.10 if int(f.get("is_starter", 0) or 0) else 0.82


def _minutes_features(features_json: object) -> dict | None:
    """Pull the D55 minutes features job1 persisted, or None if absent (job1
    couldn't reach stats.wnba.com, or no match) -> caller falls back to boost."""
    f = _features_dict(features_json)
    if "per_min_rate" not in f or "recent_minutes" not in f:
        return None
    return {
        "recent_minutes": float(f.get("recent_minutes", 0.0) or 0.0),
        "per_min_rate": float(f.get("per_min_rate", 0.0) or 0.0),
        "minutes_vol": float(f.get("minutes_vol", 5.0) or 5.0),
        "n_min_games": int(f.get("n_min_games", 0) or 0),
    }


def _cascade_bonuses(enrichment_raw: list[dict]) -> dict[int, float]:
    """Injury-cascade bonus minutes per player (D55). Built from the FULL pool
    (incl. OUT players, who are the donors) using each player's recent_minutes
    as minutes_l10. Empty when no OUT player has minutes history."""
    rows: list[CascadeInput] = []
    for r in enrichment_raw:
        mf = _minutes_features(r.get("features_json"))
        if mf is None:
            continue
        pid_raw = r.get("real_sports_player_id")
        if pid_raw is None:
            continue
        try:
            pid = int(pid_raw)
        except (TypeError, ValueError):
            continue
        rows.append(
            CascadeInput(
                player_id=pid,
                team=str(r.get("team", "") or ""),
                position=str(r.get("position", "") or ""),
                minutes_l10=mf["recent_minutes"],
                is_out=_is_out_from_features(r.get("features_json")),
            )
        )
    return redistribute_minutes(rows) if rows else {}


def _load_prior_real_scores(slate_date: str) -> dict[int, list[float]]:
    """As-of per-player realized real_scores from slate_labels for all slates
    STRICTLY BEFORE `slate_date`, most-recent-first. Drives per-player
    sampling sigma (volatility). Empty on any DB error -> caller uses the
    calibrated default sigma. Walk-forward-safe: never reads the target slate.
    """
    try:
        eng = get_engine()
    except RuntimeError:
        return {}
    q = text(
        "SELECT platform_player_id, slate_date, MAX(real_score) AS real_score "
        "FROM slate_labels WHERE slate_date < :sd AND real_score IS NOT NULL "
        "GROUP BY platform_player_id, slate_date ORDER BY slate_date DESC"
    )
    out: dict[int, list[float]] = {}
    with eng.connect() as conn:
        for row in conn.execute(q, {"sd": slate_date}):
            m = row._mapping
            pid = m.get("platform_player_id")
            rs = m.get("real_score")
            if pid is None or rs is None:
                continue
            out.setdefault(int(pid), []).append(float(rs))
    return out


def _load_measured_drafts(slate_date: str) -> dict[int, int]:
    """Pull the most recent draftStats.drafts counts from slate_labels for
    the slate. Empty if Job 2 is firing before any contest finalized
    (typical case pregame). Job 2 then falls back to the popularity
    estimator."""
    try:
        eng = get_engine()
    except RuntimeError:
        return {}
    q = text(
        "SELECT platform_player_id, MAX(drafts) AS drafts "
        "FROM slate_labels WHERE slate_date = :sd AND drafts IS NOT NULL "
        "GROUP BY platform_player_id"
    )
    with eng.connect() as conn:
        rows = conn.execute(q, {"sd": slate_date}).fetchall()
    out: dict[int, int] = {}
    for r in rows:
        m = r._mapping
        pid = m.get("platform_player_id")
        d = m.get("drafts")
        if pid is None or d is None:
            continue
        out[int(pid)] = int(d)
    return out


def _load_slate_label_names(slate_date: str) -> dict[int, str]:
    """Pull display names from slate_labels for the slate, keyed by
    platform_player_id.

    Defense-in-depth name source for the frozen lineup (D50). The primary
    name path is `job1_enrichment.name` (Real Sports pool, D49). When that
    is empty for a player, this fallback fills it from the independently
    populated `slate_labels.display_name` so the freeze never ships a
    `Player <id>` placeholder when a real name exists anywhere in the DB.
    Empty / blank names are skipped so they never shadow the final
    `Player {pid}` fallback. Empty when Job 2 fires before any contest
    finalized (typical pregame), in which case the enrichment name stands.
    """
    try:
        eng = get_engine()
    except RuntimeError:
        return {}
    q = text(
        "SELECT DISTINCT ON (platform_player_id) platform_player_id, display_name "
        "FROM slate_labels WHERE slate_date = :sd "
        "ORDER BY platform_player_id, id DESC"
    )
    with eng.connect() as conn:
        rows = conn.execute(q, {"sd": slate_date}).fetchall()
    out: dict[int, str] = {}
    for r in rows:
        m = r._mapping
        pid = m.get("platform_player_id")
        name = str(m.get("display_name", "") or "").strip()
        if pid is None or not name:
            continue
        out[int(pid)] = name
    return out


def _predict_heads_for_pool(
    art: PickerArtifact | None,
    enrichment: list[dict],
) -> dict[int, dict[str, float]]:
    """D69 / Phase 2b Tier-0: run the D63 trained heads over every pool player
    whose `head_features` row Job 1 persisted into ``features_json``.

    Returns {pid: {"p10", "p50", "p90"}} for matched players. Empty dict on:
      - artifact None / no minutes head trained (no behavioural change)
      - no pool player has head_features (cold-start day, fall through to ladder)
      - any predict failure (logged + skipped, per-player ladder still fires)
    """
    if art is None:
        return {}
    # Require both heads the recompose uses; otherwise predict_real_score returns
    # None and we save the import + frame build.
    minutes_head = art.heads.get(("minutes", "F"))
    rate_head = art.heads.get(("real_score_per_min", "F"))
    if minutes_head is None or rate_head is None:
        return {}
    feature_cols = minutes_head.feature_columns
    rate_cols = rate_head.feature_columns
    # The two heads were trained on identical _BASE_FEATURES (features/spec.py).
    # Take the union so neither booster sees a missing column at predict time.
    needed = tuple(dict.fromkeys((*feature_cols, *rate_cols)))

    pids: list[int] = []
    rows: list[dict] = []
    for r in enrichment:
        pid_raw = r.get("real_sports_player_id")
        if pid_raw is None:
            continue
        try:
            pid = int(pid_raw)
        except (TypeError, ValueError):
            continue
        f = _features_dict(r.get("features_json"))
        hf = f.get("head_features") if isinstance(f, dict) else None
        if not isinstance(hf, dict) or not hf:
            continue
        # Cohort routing inside predict_real_score reads `position`; pool into "F"
        # for now (matches features/corpus build_gamelog_corpus, D63 memory).
        row = {"position": "F"}
        for c in needed:
            v = hf.get(c, 0.0)
            try:
                row[c] = float(v) if v is not None else 0.0
            except (TypeError, ValueError):
                row[c] = 0.0
        pids.append(pid)
        rows.append(row)
    if not rows:
        return {}
    try:
        import polars as pl

        frame = pl.DataFrame(rows)
        pred = art.predict_real_score(frame)
    except Exception as exc:
        log.warning("head_predict_failed", reason=str(exc)[:160])
        return {}
    if pred is None:
        return {}
    out: dict[int, dict[str, float]] = {}
    for pid, p10, p50, p90 in zip(pids, pred["p10"], pred["p50"], pred["p90"]):
        if p50 is None or not np.isfinite(p50):
            continue
        out[int(pid)] = {
            "p10": float(p10) if np.isfinite(p10) else 0.0,
            "p50": float(p50),
            "p90": float(p90) if np.isfinite(p90) else float(p50),
        }
    log.info("head_predict", n_in=len(rows), n_out=len(out))
    return out


def _build_specs(
    enrichment: list[dict],
    *,
    slate_date: str,
    contrarian_cfg: ContrarianConfig | None = None,
    player_history: dict[int, float] | None = None,
    prior_by_player: dict[int, list[float]] | None = None,
    injury_bonus_by_pid: dict[int, float] | None = None,
) -> tuple[list[PlayerSamplingSpec], list[FieldPlayerSpec], dict[int, dict]]:
    """Build the (sampling, field) specs the optimizer reads.

    Applies the anti-popularity contrarian adjustment (basketball-main
    Finding 4) to the heuristic real_score. Popularity comes from
    measured `drafts` in slate_labels when available, else from the
    estimator (season ppg + big-market + slate size).

    Returns: (sampling_specs, field_specs, projection_by_pid). The third
    element carries the per-player display data needed to materialize
    `per_player` into the frozen JSONB (display_name, team, opponent,
    position, card_boost, final pred_real_score after contrarian).
    """
    if contrarian_cfg is None:
        s = get_settings()
        contrarian_cfg = ContrarianConfig(
            enabled=s.contrarian_enabled, strength=s.contrarian_strength
        )
    if not enrichment:
        return [], [], {}

    # Defense-in-depth name source (D50): when the Real Sports pool left
    # `job1_enrichment.name` empty, fill display names from slate_labels so
    # the frozen lineup never ships a `Player <id>` placeholder.
    label_names = _load_slate_label_names(slate_date)

    # Load trained artifact when WNBA_ORACLE_MODEL_ARTIFACT_SHA matches a
    # picker_*.pkl under models/. EB baseline predictions replace the
    # heuristic for any player seen in training; unseen players still
    # use _heuristic_real_score. None on missing/mismatched artifact
    # means the entire pool falls back to heuristic — same path as before
    # D45 wiring. This makes deployment of a new model SHA non-destructive.
    settings = get_settings()
    art = _load_model_artifact(settings.model_artifact_sha)
    # D69 / Phase 2b Tier-0: batch-predict from the D63 quantile heads up-front.
    # Empty dict means no head served (no features, no trained heads, or predict
    # failure) -- the per-player loop falls through to the existing ladder for
    # every pid not in this map, preserving the byte-identical pre-D69 freeze.
    head_predictions = _predict_heads_for_pool(art, enrichment)
    head_quantiles_by_pid: dict[int, dict[str, float]] = {}
    n_head_predicted = 0
    n_eb_predicted = 0
    n_history_fallback = 0
    n_heuristic_fallback = 0

    # Slate-size signal for the popularity estimator
    n_games_on_slate = len({str(r.get("team", "") or "") for r in enrichment if r.get("team")}) // 2
    n_games_on_slate = max(n_games_on_slate, 1)

    measured_drafts = _load_measured_drafts(slate_date)
    if measured_drafts:
        popularity_scores = slate_labels_to_popularity(measured_drafts)
        log.info("contrarian_using_measured", n_measured=len(popularity_scores))
    else:
        # Estimator fallback: use card_boost as a weak proxy for season_ppg
        # since we don't yet ingest per-player season stats. card_boost is
        # inverse to rolling Real Rating average, so 3.0 -> cold star,
        # 0.0 -> hot star. We invert it.
        popularity_scores = {}
        for r in enrichment:
            pid_raw = r.get("real_sports_player_id")
            if pid_raw is None:
                continue
            try:
                pid = int(pid_raw)
            except (TypeError, ValueError):
                continue
            boost = float(r.get("card_boost", 0.0) or 0.0)
            # Pseudo-ppg in [10, 22] from boost in [3, 0]
            pseudo_ppg = 10.0 + (3.0 - boost) * 4.0
            popularity_scores[pid] = estimate_draft_popularity(
                season_ppg=pseudo_ppg,
                team=str(r.get("team", "") or ""),
                n_games_on_slate=n_games_on_slate,
            )

    # First pass: per-player predicted real_score (heuristic) modulated by
    # the per-game game-script multiplier. The multiplier reads Vegas
    # total + spread from features_json (Job 1 persisted them). Games
    # with no Vegas signal degrade to a neutral 1.0x.
    pred_real_scores: dict[int, float] = {}
    rows_by_pid: dict[int, dict] = {}
    minutes_vol_by_pid: dict[int, float] = {}
    gsm_enabled = settings.game_script_minutes_enabled
    gsm_cfg = GameScriptMinutesConfig()
    # When the role-aware blowout redistribution is on it OWNS the blowout
    # effect, so disable the blunt team-wide blowout penalty to avoid
    # double-counting (D57).
    gs_cfg = GameScriptConfig(blowout_penalty=1.0) if gsm_enabled else GameScriptConfig()
    mcfg = MinutesConfig()
    bonus = injury_bonus_by_pid or {}
    avail_enabled = settings.availability_model_enabled
    avail_cfg = AvailabilityConfig()
    blowout_prob_by_pid: dict[int, float] = {}
    is_starter_by_pid: dict[int, bool] = {}
    is_anchor_by_pid: dict[int, bool] = {}
    p_active_by_pid: dict[int, float] = {}
    gsm_rows: list[GameScriptInput] = []
    rate_by_pid: dict[int, float] = {}
    n_minutes_predicted = 0
    for r in enrichment:
        pid_raw = r.get("real_sports_player_id")
        if pid_raw is None:
            continue
        try:
            pid = int(pid_raw)
        except (TypeError, ValueError):
            continue
        boost = float(r.get("card_boost", 0.0) or 0.0)
        position = str(r.get("position", "") or "")
        total, spread = _vegas_from_features(r.get("features_json"))
        gs_mult = game_script_multiplier(total, spread, cfg=gs_cfg) if total > 0 else 1.0
        f = _features_dict(r.get("features_json"))
        mf = _minutes_features(r.get("features_json")) if settings.minutes_model_enabled else None
        # Anchor flag (D57, Tier 1) -- computed regardless of the floor setting
        # so it always rides on the spec; the optimizer only enforces it when
        # min_anchors > 0.
        is_anchor_by_pid[pid] = (
            mf is not None
            and mf["n_min_games"] >= ANCHOR_MIN_GAMES
            and mf["recent_minutes"] >= ANCHOR_MIN_MINUTES
        ) or (
            bool(int(f.get("rotowire_confirmed", 0) or 0))
            and bool(int(f.get("is_starter", 0) or 0))
        )
        if avail_enabled:
            p_active_by_pid[pid] = availability_probability(
                recent_minutes=float(mf["recent_minutes"]) if mf is not None else 0.0,
                minutes_vol=float(mf["minutes_vol"]) if mf is not None else 0.0,
                n_min_games=int(mf["n_min_games"]) if mf is not None else 0,
                rotowire_confirmed=bool(int(f.get("rotowire_confirmed", 0) or 0)),
                is_starter=bool(int(f.get("is_starter", 0) or 0)),
                cfg=avail_cfg,
            )
        if gsm_enabled and total > 0:
            # Blowout context for the regime-switching copula + the minutes
            # redistribution (D57). Only players with known recent minutes can
            # donate/receive; cold-start darts have no minutes and so are left
            # untouched here (the availability engine, not this, gates them).
            blowout_prob_by_pid[pid] = blowout_probability(abs(spread), gsm_cfg)
            recent_min_gs = float(mf["recent_minutes"]) if mf is not None else 0.0
            is_starter_by_pid[pid] = (
                bool(int(f.get("is_starter", 0) or 0))
                or recent_min_gs >= gsm_cfg.starter_minutes_floor
            )
            if mf is not None and recent_min_gs > 0.0:
                gsm_rows.append(
                    GameScriptInput(pid, str(r.get("team", "") or ""), recent_min_gs, abs(spread))
                )
                rate_by_pid[pid] = float(mf["per_min_rate"])
        # D69 / Phase 2b Tier-0: trained quantile heads (D63). Walk-forward
        # validated corr 0.554 vs the existing ladder's 0.246. Falls through to
        # Tier 1 (blended_real_score) for any pid the head didn't score.
        hp = head_predictions.get(pid)
        if hp is not None:
            p10 = hp["p10"]
            p50 = hp["p50"]
            p90 = hp["p90"]
            # Game-script multiplier still applies (Vegas tilt on top of the
            # head). Floor matches every other Tier so the downstream sampler
            # never sees a non-positive mean.
            pred_real_scores[pid] = max(0.5, p50 * gs_mult)
            # 80% interval (~2.56 sigma) -> additive real_score volatility. Same
            # semantic as `minutes_vol_by_pid` for the Tier-1 path so the
            # sampler's delta-method conversion works unchanged.
            spread = max(0.0, p90 - p10) / 2.56
            minutes_vol_by_pid[pid] = max(0.5, spread)
            head_quantiles_by_pid[pid] = {"p10": p10, "p50": p50, "p90": p90}
            n_head_predicted += 1
            rows_by_pid[pid] = r
            continue
        if mf is not None and mf["n_min_games"] >= mcfg.min_obs_for_history:
            # D55 minutes edge: blended_real_score handles the boost<->minutes
            # weighting internally, with same-day role signals. Blowout is left
            # to game_script (it already penalises via the spread tier) to avoid
            # double-counting; the starter multiplier is superseded by the
            # confirmed-role minutes anchor here, so it is NOT applied.
            base = blended_real_score(
                recent_min=mf["recent_minutes"],
                rate=mf["per_min_rate"],
                n_games=mf["n_min_games"],
                boost_prior=_heuristic_real_score(boost),
                rotowire_confirmed=bool(int(f.get("rotowire_confirmed", 0) or 0)),
                is_starter=bool(int(f.get("is_starter", 0) or 0)),
                injury_bonus_min=float(bonus.get(pid, 0.0)),
                blowout=False,
                cfg=mcfg,
            )
            pred_real_scores[pid] = max(0.5, base * gs_mult)
            minutes_vol_by_pid[pid] = mf["minutes_vol"] * mf["per_min_rate"]
            n_minutes_predicted += 1
            rows_by_pid[pid] = r
            continue
        # Fallback (no minutes match): EB > corpus history > boost heuristic,
        # with the legacy starter nudge.
        starter_mult = _starter_multiplier(
            r.get("features_json"), enabled=settings.starter_signal_enabled
        )
        eb_pred = _eb_predict_one(art, pid, position)
        if eb_pred is not None:
            base = eb_pred
            n_eb_predicted += 1
        elif player_history is not None and pid in player_history:
            # Use observed per-player mean from the training corpus. More
            # accurate than the generic heuristic for players whose data
            # postdates the last training run (common early-season pattern).
            base = max(0.5, player_history[pid])
            n_history_fallback += 1
        else:
            base = _heuristic_real_score(boost)
            n_heuristic_fallback += 1
        pred_real_scores[pid] = max(0.5, base * gs_mult * starter_mult)
        rows_by_pid[pid] = r

    if gsm_enabled and gsm_rows:
        # Convert the signed minute deltas to real_score via each player's
        # per-minute rate, then fold into pred_real_score (D57). Bench up,
        # starters down; floored at 0.5 like every other predictor branch.
        deltas_min = redistribute_game_script_minutes(gsm_rows, gsm_cfg)
        n_bumped = sum(1 for d in deltas_min.values() if d > 0)
        n_trimmed = sum(1 for d in deltas_min.values() if d < 0)
        for pid_d, dmin in deltas_min.items():
            rate = rate_by_pid.get(pid_d, mcfg.league_rate)
            pred_real_scores[pid_d] = max(0.5, pred_real_scores[pid_d] + dmin * rate)
        log.info(
            "game_script_minutes", n_bumped=n_bumped, n_trimmed=n_trimmed, n_rows=len(gsm_rows)
        )

    log.info(
        "predictor_mix",
        artifact_sha=settings.model_artifact_sha[:12] if settings.model_artifact_sha else "",
        n_head_predicted=n_head_predicted,
        n_minutes_predicted=n_minutes_predicted,
        n_eb_predicted=n_eb_predicted,
        n_history_fallback=n_history_fallback,
        n_heuristic_fallback=n_heuristic_fallback,
    )

    if avail_enabled and p_active_by_pid:
        # Two-part hurdle (D57, Tier 2): scale each active-conditional pred by
        # P(active). Cold-start darts collapse; established players ~unchanged.
        n_low = 0
        for pid_a, p_act in p_active_by_pid.items():
            if pid_a in pred_real_scores:
                pred_real_scores[pid_a] = max(0.5, pred_real_scores[pid_a] * p_act)
                if p_act < 0.5:
                    n_low += 1
        log.info("availability_model", n_players=len(p_active_by_pid), n_low_availability=n_low)

    # Apply contrarian adjustment
    adjusted = apply_contrarian_adjustment(pred_real_scores, popularity_scores, contrarian_cfg)

    # Per-player sampling sigma from volatility (D52/D55). A flat sigma priced
    # every player the same; ceiling plays (high game-to-game variance) should
    # sample wider so the EV/percentile math sees their upside. Prefer the
    # minutes-derived volatility (minutes_vol x rate, D55) for matched players,
    # else fall back to realized real_score volatility. K and sigma share the
    # same score_offset the copula un-offsets.
    K = float(settings.sampling_score_offset)
    volatility = player_volatility(prior_by_player or {})

    samps: list[PlayerSamplingSpec] = []
    fields: list[FieldPlayerSpec] = []
    projection_by_pid: dict[int, dict] = {}
    for pid, pred in adjusted.items():
        r = rows_by_pid[pid]
        team = str(r.get("team", "") or "")
        opp = str(r.get("opponent", "") or "")
        boost = float(r.get("card_boost", 0.0) or 0.0)
        mu_log = float(np.log(max(pred + K, 1.0)))
        # Convert the real_score-unit volatility to a log-scale sigma via the
        # delta method: std(real) ~= (pred + K) * sigma_log. Clamp to a sane
        # band so a single outlier game can't blow up the percentile bias.
        vol = minutes_vol_by_pid.get(int(pid)) or volatility.get(int(pid), 1.17)
        sigma_log = min(0.6, max(0.12, vol / max(pred + K, 1e-6)))
        samps.append(
            PlayerSamplingSpec(
                player_id=pid,
                team=team,
                opponent=opp,
                mu=mu_log,
                sigma=sigma_log,
                boost=boost,
                is_starter=is_starter_by_pid.get(pid, False),
                blowout_prob=blowout_prob_by_pid.get(pid, 0.0),
                is_anchor=is_anchor_by_pid.get(pid, False),
            )
        )
        fields.append(
            FieldPlayerSpec(
                player_id=pid,
                pred_real_score=pred,
                card_boost=boost,
            )
        )
        enrichment_name = str(r.get("name", "") or "").strip()
        display_name = enrichment_name or label_names.get(pid, "") or f"Player {pid}"
        proj = {
            "display_name": display_name,
            "team": team,
            "opponent": opp,
            "position": str(r.get("position", "") or "F"),
            "card_boost": boost,
            "pred_real_score_p50": pred,
        }
        # D69 / Phase 2b: surface the head quantiles when Tier-0 served this
        # pid. The frontend (_build_per_player) reads p10/p90 to draw the
        # real_score interval; absent for ladder-served players (unchanged).
        hq = head_quantiles_by_pid.get(pid)
        if hq is not None:
            proj["pred_real_score_p10"] = float(hq["p10"])
            proj["pred_real_score_p90"] = float(hq["p90"])
        projection_by_pid[pid] = proj
    return samps, fields, projection_by_pid


FROZEN_INSERT = text(
    """
    INSERT INTO frozen_lineups (
        slate_date, model_sha, payout_regime, frozen_at, lineup,
        entry_recommendation, expected_payout, metadata_json
    ) VALUES (
        :slate_date, :model_sha, :payout_regime, now(), CAST(:lineup AS JSONB),
        :entry_recommendation, :expected_payout, CAST(:metadata_json AS JSONB)
    )
    ON CONFLICT (slate_date, model_sha) DO NOTHING
    RETURNING id;
    """
)

FROZEN_EXISTS = text("SELECT 1 FROM frozen_lineups WHERE slate_date = :sd AND model_sha = :ms")


def _build_per_player(
    rec: LineupRecommendation,
    projection_by_pid: dict[int, dict],
) -> list[dict]:
    """Materialize the per-player projection list embedded in the frozen
    lineup JSONB. The frontend's FrozenLineup contract reads this to
    render player names, teams, opponents, positions, boosts, and the
    minutes-quantile interval bar.

    The picker does not yet produce per-player minutes quantiles (no
    minutes model is trained against the slate-labels corpus). Until
    that lands we synthesize a calibrated interval anchored on a
    rank-aware default consistent with WNBA observed starter minutes
    (high-floor starter centered ~30 with ~6 min spread). The minutes
    field is documented as best-effort so a future model can swap in
    without a schema change.
    """
    pid_order = list(rec.player_ids)
    out: list[dict] = []
    for slot_idx, pid in enumerate(pid_order):
        proj = projection_by_pid.get(int(pid), {})
        # Rank-aware minutes default. Slot 1 (top value) leans starter
        # heavy; slot 5 trails because boost-elevated benchers tend to
        # land here. Symmetric ±4 spread anchors P10/P90 around the
        # observed WNBA starter range.
        p50 = max(22.0, 32.0 - 1.5 * slot_idx)
        entry = {
            "player_id": int(pid),
            "display_name": proj.get("display_name", f"Player {pid}"),
            "team": proj.get("team", ""),
            "opponent": proj.get("opponent", ""),
            "position": proj.get("position", "F"),
            "card_boost": float(proj.get("card_boost", 0.0)),
            "pred_real_score_p50": float(proj.get("pred_real_score_p50", 0.0)),
            "pred_minutes_p10": p50 - 4.0,
            "pred_minutes_p50": p50,
            "pred_minutes_p90": p50 + 4.0,
        }
        # D69 / Phase 2b: pass through the real_score interval when the
        # trained heads served this player. The synthetic minutes interval
        # above remains the placeholder until a minutes-quantile passthrough
        # ships in a follow-up; absent fields are backward-compatible.
        if "pred_real_score_p10" in proj:
            entry["pred_real_score_p10"] = float(proj["pred_real_score_p10"])
            entry["pred_real_score_p90"] = float(proj["pred_real_score_p90"])
        out.append(entry)
    return out


def _freeze(
    slate_date: str,
    model_sha: str,
    rec: LineupRecommendation,
    payout_regime: str,
    projection_by_pid: dict[int, dict],
) -> bool:
    """Idempotent freeze: first job2 fire writes, subsequent fires no-op.

    True-freeze semantics (the operator submits one lineup per slate and
    must not see it change underneath them):

    1. Check Postgres for an existing row keyed on (slate_date, model_sha).
       Existence is the canonical "already frozen" signal — Redis is just
       a fast-path hint.
    2. If absent, take the Redis SETNX lock as a fast soft-lock to
       discourage concurrent inserts within the cron window (cron-job2
       fires every 15 min; without the lock two cron tasks could race
       between the existence-check and the INSERT). On lock-miss treat
       it as "another fire is in flight" and bail without writing.
    3. Issue an INSERT ... ON CONFLICT DO NOTHING. If a parallel writer
       won the race we still get a clean no-op return. ``RETURNING id``
       distinguishes "I wrote this row" from "row already existed".

    Returns True iff this invocation wrote the freeze record. Subsequent
    fires return False and log ``job2_already_frozen`` — the lineup
    columns are not touched.
    """
    eng = get_engine()
    with eng.connect() as conn:
        existing = conn.execute(FROZEN_EXISTS, {"sd": slate_date, "ms": model_sha}).first()
    if existing:
        log.info("job2_already_frozen", slate_date=slate_date, model_sha=model_sha)
        return False

    rd = get_redis()
    key = f"wnba.frozen.{slate_date}"
    # The 24h TTL covers a full slate window; if the writer crashes the
    # lock auto-releases for the next fire to retry.
    lock_acquired = bool(rd.set(key, model_sha, nx=True, ex=24 * 3600))
    if not lock_acquired:
        log.info(
            "job2_freeze_lock_held",
            slate_date=slate_date,
            note="another job2 fire is mid-freeze; deferring",
        )
        return False

    payload = {
        "slate_date": slate_date,
        "model_sha": model_sha,
        "payout_regime": payout_regime,
        "lineup": json.dumps(
            {
                "player_ids": list(rec.player_ids),
                "slot_multipliers": list(rec.slot_multipliers),
                "lineup_score_p10": rec.lineup_score_p10,
                "lineup_score_p50": rec.lineup_score_p50,
                "lineup_score_p90": rec.lineup_score_p90,
                "per_player": _build_per_player(rec, projection_by_pid),
            }
        ),
        "entry_recommendation": rec.entry_flag,
        "expected_payout": rec.expected_payout,
        "metadata_json": json.dumps({"frozen_via": "job2_first_fire"}),
    }
    with eng.begin() as conn:
        result = conn.execute(FROZEN_INSERT, payload).first()
    if result is None:
        # ON CONFLICT DO NOTHING fired between our existence check and
        # the INSERT (rare; Redis lock should have prevented it). Treat
        # as "we lost the race".
        log.info("job2_lost_insert_race", slate_date=slate_date)
        return False
    log.info("job2_frozen", slate_date=slate_date, row_id=int(result[0]))
    return True


def run(slate_date: str | None = None, *, dry_run: bool = False) -> Job2Result:
    settings = get_settings()
    sd = slate_date or dt.date.today().isoformat()
    model_sha = settings.model_artifact_sha or "heuristic-v1"

    log.info("job2_start", slate_date=sd, model_sha=model_sha)
    enrichment_raw = _load_enrichment(sd)
    # Injury cascade (D55): redistribute OUT players' recent minutes to active
    # teammates BEFORE dropping the OUT players from the pool (they are the
    # donors). job1 now ships recent_minutes per player, so the full D33/D29
    # cascade finally has the mins_l10 it needs. Empty when no OUT player has
    # minutes history.
    injury_bonus = _cascade_bonuses(enrichment_raw)
    if injury_bonus:
        log.info(
            "job2_injury_cascade",
            n_recipients=len(injury_bonus),
            max_bonus=round(max(injury_bonus.values()), 1),
        )
    # RotoWire OUT players are excluded from the optimizer pool (the binary
    # drop is the other half of the cascade).
    enrichment = [r for r in enrichment_raw if not _is_out_from_features(r.get("features_json"))]
    n_dropped = len(enrichment_raw) - len(enrichment)
    if n_dropped:
        log.info("job2_dropped_out_players", n_dropped=n_dropped, n_remaining=len(enrichment))
    if len(enrichment) < 5:
        log.warning("job2_pool_too_small", n=len(enrichment), n_dropped=n_dropped)
        return Job2Result(sd, model_sha, None, False, "pool_too_small")

    player_history = _load_player_history()
    prior_by_player = _load_prior_real_scores(sd)
    log.info(
        "player_history_loaded",
        n_players=len(player_history),
        n_prior_history=len(prior_by_player),
    )
    samps, fields, projection_by_pid = _build_specs(
        enrichment,
        slate_date=sd,
        player_history=player_history,
        prior_by_player=prior_by_player,
        injury_bonus_by_pid=injury_bonus,
    )
    if len(samps) < 5:
        return Job2Result(sd, model_sha, None, False, "specs_too_small")

    curve = load_curve_from_archive(sd) or default_curve_for_regime(settings.payout_regime)
    cfg = OptimizeConfig(
        top_n_filter=settings.optimizer_top_n_filter,
        n_samples=settings.optimizer_n_samples,
        n_field_lineups=settings.optimizer_n_field_lineups,
        max_per_team=settings.optimizer_max_per_team,
        dynamic_team_cap=settings.optimizer_dynamic_team_cap,
        caveat_is_skip=settings.caveat_is_skip,
        never_skip=settings.never_skip,
        score_offset=settings.sampling_score_offset,
        min_anchors=settings.lineup_anchor_floor,
        boost_sum_cap=settings.optimizer_boost_sum_cap,
        max_single_boost=settings.optimizer_max_single_boost,
        game_stack_bonus=settings.optimizer_game_stack_bonus,
    )
    rec = optimize_lineup(samps, fields, curve, cfg=cfg)
    log.info(
        "job2_optimizer_done",
        n_pool=len(samps),
        expected_payout=rec.expected_payout,
        entry_flag=rec.entry_flag,
    )
    if dry_run:
        return Job2Result(sd, model_sha, rec, False, "dry_run")
    frozen = _freeze(sd, model_sha, rec, curve.regime, projection_by_pid)
    return Job2Result(sd, model_sha, rec, frozen, "ok" if frozen else "already_frozen")


def main() -> int:
    configure_logging("INFO")
    settings = get_settings()
    sd = dt.date.today().isoformat()
    try:
        result = run(sd, dry_run=settings.job2_dry_run)
    except Exception as exc:
        log.exception("job2_failed", error=str(exc))
        return 1
    if result.recommendation is None:
        return 0
    return 0
