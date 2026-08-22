"""Per-slate loss ledger: where our frozen lineup lost points, and why.

Answers "did we lose a slate we should have won, and would proposal X have
caught it?" for the last N finalized slates. Reads-only against prod
Postgres. No new tables; no cron. Run on demand before deciding what to
build next.

For each finalized slate (has a frozen lineup AND slate_labels for its
five picks AND a captured leaderboard):

  1. Compute our realized lineup score with the slots taken AS COMMITTED,
     via wnba_oracle.eval.contest_score.committed_order_score:
         final = sum_i real_score_i * (card_boost_i + slot_base_i)
     with slot_base in (2.0, 1.8, 1.6, 1.4, 1.2) in frozen lineup order. See
     score_lineup for why this is not ranked by real_score.

  2. Compare against the captured top-20 median score.

  3. Swap-one exercise: for each of our five picks, sweep every pool player
     (job1_enrichment at that slate) with a realized real_score, and record
     the single-slot substitution that would have gained the most contest
     points. Report the top swap plus a categorization of why we missed it:
         - "boost_underweight": alt had higher card_boost than the pick
         - "starter_signal": alt was expected starter but the pick was not
         - "prop_signal_pos": alt had strong over prob we discounted
         - "model_underrate": alt's per-min-rate features were competitive
         - "unclassified": pool-included, none of the above

Output:
  - Stdout: a compact table for eyeballing (default 20 slates).
  - --csv PATH: also write the full ledger to CSV.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

from sqlalchemy import text  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402

from wnba_oracle.db.engine import get_engine  # noqa: E402
from wnba_oracle.eval.contest_score import DEFAULT_SLOT_BASES, committed_order_score  # noqa: E402

SLOT_MULTIPLIERS = DEFAULT_SLOT_BASES
MAX_SLOT_MULT = SLOT_MULTIPLIERS[0]

# 2026-07-04 counterfactual knob values (see calibrate_starter_and_boost.py).
STARTER_UNKNOWN_FADE = 0.75
STARTER_MULT = 1.10
CONFIRMED_BENCH_MULT = 0.82
BOOST_TAIL_LIFT_THRESHOLD = 2.0
BOOST_TAIL_LIFT_FACTOR = 1.5
# 2026-07-10 suite overlays. The starter-min-lift parameters live on
# job2_scoring._starter_minutes_lift defaults; these two mirror the armed
# PICKER_FLOOR_TILT_* prod values. Weight is deliberately gentle: the sweep
# showed a cliff at 0.35 (suite total_delta -47.7) because a strong tilt
# demotes stable veterans enough that minutes-lifted spike-tier players
# (exempt from the tilt) flood the top-5; 0.2 keeps the suite at +12.5 vs
# the fade-only incumbent with the best win rate (14 up / 9 down).
FLOOR_TILT_WEIGHT = 0.2
FLOOR_TILT_MAX_BOOST = 2.0

# Live picker constraints replicated in the counterfactual so its top-5
# reflects what the freeze would actually ship. See STATUS.md
# "Active Railway env vars" for the source of truth.
LIVE_ANCHOR_FLOOR = 2  # LINEUP_ANCHOR_FLOOR
LIVE_MAX_PER_TEAM = 2  # OPTIMIZER_MAX_PER_TEAM
LIVE_MAX_SINGLE_BOOST = 3.0  # OPTIMIZER_MAX_SINGLE_BOOST (raised 2026-07-04, e1be74d)
LIVE_BOOST_SUM_CAP = 9.0  # OPTIMIZER_BOOST_SUM_CAP
# Anchor definition mirrors job2.ANCHOR_MIN_GAMES / ANCHOR_MIN_MINUTES.
LIVE_ANCHOR_MIN_GAMES = 3
LIVE_ANCHOR_MIN_MINUTES = 20.0


@dataclass
class PlayerLine:
    pid: int
    name: str
    team: str
    position: str
    card_boost: float
    real_score: float
    # features_json bits used for categorization (all optional)
    is_starter: int = 0
    rotowire_confirmed: int = 0
    is_out: int = 0
    prop_over_prob: float | None = None
    prop_line: float | None = None
    recent_minutes: float | None = None
    per_min_rate: float | None = None


@dataclass
class SwapCandidate:
    slot: int
    pick: PlayerLine
    alt: PlayerLine
    gain: float
    category: str


@dataclass
class SlateEntry:
    slate_date: str
    contest_id: int | None
    model_sha: str
    freeze_seq: int
    our_picks: list[PlayerLine]
    our_score: float
    top20_median: float | None
    top20_min: float | None
    winner_score: float | None
    delta_vs_median: float | None
    n_captured: int
    n_pool_scored: int  # pool players with a realized real_score
    top_swap: SwapCandidate | None = None
    all_swaps_top5: list[SwapCandidate] = field(default_factory=list)


def score_lineup(players: list[PlayerLine]) -> float:
    """Contest score for a five-player lineup, slots taken AS COMMITTED.

    ``players`` must already be in slot order: index 0 holds the 2.0x base.
    Every caller satisfies that. ``our_picks`` follows the frozen lineup's
    ``player_ids``, which is the order we submitted; ``chosen`` comes out of the
    counterfactual optimizer in its recommended order; the swap-one trial keeps
    our order and replaces one slot in place.

    Before 2026-08-19 this sorted by realized ``real_score`` first, mirroring
    ``picker.sample.lineup_score_samples``. That is hindsight: it hands the 2.0x
    slot to whoever happened to spike, which no entrant can do. It inflated
    ``our_score``, and it inflated every swap gain more, because a substituted
    player was silently re-slotted to wherever they scored best. Any tuning
    number in git history that cites this script predates the fix and is not
    comparable with a number produced after it.
    """
    if len(players) != 5:
        return 0.0
    return committed_order_score(
        [p.real_score for p in players],
        [p.card_boost for p in players],
        SLOT_MULTIPLIERS,
    )


def categorize_swap(pick: PlayerLine, alt: PlayerLine) -> str:
    """Categorize why our lineup passed on `alt` in favor of `pick`.

    Priority order matches operator judgment: boost gaps are the easiest to
    audit, then starter signal, then prop signal, then generic model
    underrate. `unclassified` = alt looks equivalent on the surface, so
    the miss is likely in the head predictions themselves.
    """
    if alt.card_boost > pick.card_boost + 0.15:
        return "boost_underweight"
    alt_expected = bool(alt.is_starter) and (bool(alt.rotowire_confirmed) or bool(alt.is_starter))
    pick_expected = bool(pick.is_starter) and (
        bool(pick.rotowire_confirmed) or bool(pick.is_starter)
    )
    if alt_expected and not pick_expected:
        return "starter_signal"
    if (
        alt.prop_over_prob is not None
        and alt.prop_over_prob >= 0.60
        and (pick.prop_over_prob is None or pick.prop_over_prob < alt.prop_over_prob - 0.05)
    ):
        return "prop_signal_pos"
    if (
        alt.per_min_rate is not None
        and alt.recent_minutes is not None
        and pick.per_min_rate is not None
        and pick.recent_minutes is not None
    ):
        alt_ceil = alt.per_min_rate * alt.recent_minutes
        pick_ceil = pick.per_min_rate * pick.recent_minutes
        if alt_ceil > pick_ceil * 1.10:
            return "model_underrate"
    return "unclassified"


def build_pool_index(rows: list[dict]) -> dict[int, PlayerLine]:
    """From a slate's job1_enrichment rows, build pid -> PlayerLine with
    features_json fields extracted for categorization. real_score is filled
    in later from slate_labels; card_boost lives on the enrichment row."""
    out: dict[int, PlayerLine] = {}
    for r in rows:
        pid = int(r["player_id"])
        f_raw = r.get("features_json") or {}
        f = f_raw if isinstance(f_raw, dict) else json.loads(f_raw) if f_raw else {}
        line = PlayerLine(
            pid=pid,
            name=r.get("name") or "",
            team=r.get("team") or "",
            position=r.get("position") or "",
            card_boost=float(r.get("card_boost") or 0.0),
            real_score=0.0,
            is_starter=int(f.get("is_starter", 0) or 0),
            rotowire_confirmed=int(f.get("rotowire_confirmed", 0) or 0),
            is_out=int(f.get("is_out", 0) or 0),
            prop_over_prob=(
                float(f["prop_points_over_prob"])
                if f.get("prop_points_over_prob") is not None
                else None
            ),
            prop_line=(
                float(f["prop_points_line"]) if f.get("prop_points_line") is not None else None
            ),
            recent_minutes=(
                float(f["recent_minutes"]) if f.get("recent_minutes") is not None else None
            ),
            per_min_rate=(float(f["per_min_rate"]) if f.get("per_min_rate") is not None else None),
        )
        out[pid] = line
    return out


def _apply_overlay(
    pred_p50: float,
    pred_p90: float,
    boost: float,
    is_starter: int,
    rotowire_confirmed: int,
    overlay: str,
    pred_p10: float = 0.0,
    features: dict | None = None,
) -> tuple[float, float]:
    """Return (adjusted_pred, adjusted_p90) after applying the overlay.

    - "starter-fade": unknowns (both flags 0) get STARTER_UNKNOWN_FADE; expected
      starters keep the existing 1.10 boost; confirmed benches keep 0.82.
    - "boost-lift": for boost >= BOOST_TAIL_LIFT_THRESHOLD, promote pred to p90
      so the ranker sees ceiling.
    - "both": stack starter-fade + boost-lift.
    - "starter-min-lift": starter-fade + the 2026-07-10 minutes-conditional
      starter lift (expected starters with lagging recent minutes get
      blended up toward the starter norm; the Kuier/Harris fix).
    - "floor-tilt": starter-fade + blend non-spike candidates' rank center
      toward p10 (the Ogunbowale-vs-Shepard fix).
    - "suite": starter-fade + starter-min-lift + floor-tilt (boost-lift
      stays off, matching its 2026-07-04 prod rollback).

    The output feeds a heuristic rank score adjusted_pred * (2 + boost) that
    stands in for the picker's stage-1 filter without needing the full
    optimizer.
    """
    from wnba_oracle.scheduler.job2_scoring import (
        _floor_tilt_multiplier,
        _starter_minutes_lift,
    )

    fade_on = overlay in ("starter-fade", "both", "starter-min-lift", "floor-tilt", "suite")
    # Starter multiplier
    if is_starter == 0 and rotowire_confirmed == 0:
        mult = STARTER_UNKNOWN_FADE if fade_on else 1.0
    elif rotowire_confirmed == 1 and is_starter == 0:
        mult = CONFIRMED_BENCH_MULT
    else:
        mult = STARTER_MULT
    if overlay in ("starter-min-lift", "suite"):
        mult *= _starter_minutes_lift(features or {}, enabled=True)
    # Boost-tail lift: multiplicative ceiling nudge (calibrated 1.5 =
    # empirical mean_real/mean_p50 ratio at boost>=2.0), applied to the
    # ranker's pred_p50. Matches src/wnba_oracle/scheduler/job2.py:572.
    if overlay in ("boost-lift", "both") and boost >= BOOST_TAIL_LIFT_THRESHOLD:
        rank_center = pred_p50 * BOOST_TAIL_LIFT_FACTOR
    else:
        rank_center = pred_p50
    if overlay in ("floor-tilt", "suite"):
        rank_center *= _floor_tilt_multiplier(
            pred_p10, pred_p50, boost, weight=FLOOR_TILT_WEIGHT, max_boost=FLOOR_TILT_MAX_BOOST
        )
    return rank_center * mult, pred_p90 * mult


_OFF_OVERLAY = "off"
Candidate = tuple[int, float, float, str, bool]


def _counterfactual_inputs(
    eng: Engine, slate_date: str
) -> tuple[dict[int, tuple[float, float]], list[dict]]:
    with eng.connect() as conn:
        labels = {
            int(r._mapping["platform_player_id"]): (
                float(r._mapping["card_boost"] or 0.0),
                float(r._mapping["real_score"] or 0.0),
            )
            for r in conn.execute(
                text(
                    "SELECT platform_player_id, card_boost, real_score "
                    "FROM slate_labels WHERE slate_date = :sd AND real_score IS NOT NULL"
                ),
                {"sd": slate_date},
            ).fetchall()
        }
        pool_rows = [
            dict(r._mapping)
            for r in conn.execute(
                text(
                    "SELECT player_id, name, team, position, card_boost, features_json "
                    "FROM job1_enrichment WHERE slate_date = :sd"
                ),
                {"sd": slate_date},
            ).fetchall()
        ]
    return labels, pool_rows


def _counterfactual_candidates(
    pool_rows: list[dict],
    heads: dict,
    overlay: str,
    max_single_boost: float,
) -> list[Candidate]:
    candidates: list[Candidate] = []
    for row in pool_rows:
        pid = int(row["player_id"])
        hp = heads.get(pid)
        if hp is None:
            continue
        raw_features = row.get("features_json") or {}
        features = (
            raw_features
            if isinstance(raw_features, dict)
            else json.loads(raw_features)
            if raw_features
            else {}
        )
        if bool(int(features.get("is_out", 0) or 0)):
            continue
        boost = float(row.get("card_boost") or 0.0)
        if max_single_boost > 0.0 and boost > max_single_boost:
            continue
        is_starter = int(features.get("is_starter", 0) or 0)
        rotowire_confirmed = int(features.get("rotowire_confirmed", 0) or 0)
        has_rotation = (
            int(features.get("n_min_games", 0) or 0) >= LIVE_ANCHOR_MIN_GAMES
            and float(features.get("recent_minutes", 0.0) or 0.0) >= LIVE_ANCHOR_MIN_MINUTES
        )
        is_anchor = has_rotation or (
            (rotowire_confirmed == 1 or is_starter == 1) and is_starter == 1
        )
        adjusted, _ = _apply_overlay(
            pred_p50=hp["p50"],
            pred_p90=hp["p90"],
            boost=boost,
            is_starter=is_starter,
            rotowire_confirmed=rotowire_confirmed,
            overlay=overlay,
            pred_p10=float(hp.get("p10", 0.0)),
            features=features,
        )
        candidates.append(
            (pid, adjusted * (MAX_SLOT_MULT + boost), boost, row.get("team") or "", is_anchor)
        )
    return sorted(candidates, key=lambda item: item[1], reverse=True)


def _pick_five(candidates: list[Candidate], boost_sum_cap: float) -> list[int]:
    chosen: list[Candidate] = []
    team_counts: dict[str, int] = {}
    boost_sum = 0.0
    for candidate in candidates:
        _, _, boost, team, _ = candidate
        if len(chosen) == 5:
            break
        if team and team_counts.get(team, 0) >= LIVE_MAX_PER_TEAM:
            continue
        if boost_sum_cap > 0.0 and boost_sum + boost > boost_sum_cap:
            continue
        chosen.append(candidate)
        boost_sum += boost
        if team:
            team_counts[team] = team_counts.get(team, 0) + 1

    anchor_count = sum(1 for *_, is_anchor in chosen if is_anchor)
    chosen_ids = {pid for pid, *_ in chosen}
    for anchor in (item for item in candidates if item[0] not in chosen_ids and item[4]):
        if anchor_count >= LIVE_ANCHOR_FLOOR:
            break
        for index in range(len(chosen) - 1, -1, -1):
            _, _, dropped_boost, dropped_team, dropped_anchor = chosen[index]
            if dropped_anchor:
                continue
            new_boost = boost_sum - dropped_boost + anchor[2]
            if boost_sum_cap > 0.0 and new_boost > boost_sum_cap:
                continue
            next_counts = dict(team_counts)
            if dropped_team:
                next_counts[dropped_team] -= 1
            if anchor[3] and next_counts.get(anchor[3], 0) >= LIVE_MAX_PER_TEAM:
                continue
            if anchor[3]:
                next_counts[anchor[3]] = next_counts.get(anchor[3], 0) + 1
            chosen[index] = anchor
            boost_sum = new_boost
            team_counts = next_counts
            anchor_count += 1
            break
    return [pid for pid, *_ in chosen]


def _score_counterfactual(
    entry: SlateEntry,
    chosen: list[int],
    labels: dict[int, tuple[float, float]],
) -> dict:
    lineup = [
        PlayerLine(
            pid=pid,
            name=f"pid={pid}",
            team="",
            position="",
            card_boost=labels.get(pid, (0.0, 0.0))[0],
            real_score=labels.get(pid, (0.0, 0.0))[1],
        )
        for pid in chosen
    ]
    new_score = score_lineup(lineup)
    return {
        "slate": entry.slate_date,
        "old": entry.our_score,
        "new": new_score,
        "delta": new_score - entry.our_score,
        "gap_before": entry.delta_vs_median if entry.delta_vs_median is not None else 0.0,
        "gap_after": (entry.top20_median - new_score if entry.top20_median is not None else None),
        "top20_median": entry.top20_median,
        "chosen": chosen,
    }


def _run_counterfactual(
    ledger: list[SlateEntry],
    overlay: str,
    verbose: bool = False,
    max_single_boost: float = LIVE_MAX_SINGLE_BOOST,
    boost_sum_cap: float = LIVE_BOOST_SUM_CAP,
) -> list[dict]:
    """Re-pick top-5 for each slate under the overlay, score against realized
    labels, return per-slate deltas. Uses the same current model artifact the
    picker consumes in prod so pred_p50/p90 track live behavior.

    Heuristic selection matches the picker's stage-1 filter:
        score(pid) = adjusted_pred(pid, overlay) * (2 + card_boost)
    Take the top-5 pids by that score, subject to no more than 2 per team
    (matches OPTIMIZER_MAX_PER_TEAM=2), then contest-score them.
    """
    from wnba_oracle.scheduler.job2 import _load_model_artifact, _predict_heads_for_pool

    sha = os.environ.get(
        "WNBA_ORACLE_MODEL_ARTIFACT_SHA",
        "94f8e8606dab4d48652929bb3884fb9152e1abc766eeb2c2d86559f4318676cd",
    )
    art = _load_model_artifact(sha)
    if art is None:
        raise SystemExit(f"model artifact {sha[:12]} not resolvable; re-run oracle-train?")

    eng = get_engine()
    results: list[dict] = []
    for e in ledger:
        labels, pool_rows = _counterfactual_inputs(eng, e.slate_date)
        if not pool_rows:
            continue
        enrichment = [
            {
                "real_sports_player_id": r["player_id"],
                "team": r.get("team") or "",
                "opponent": "",
                "position": r.get("position") or "F",
                "card_boost": float(r.get("card_boost") or 0.0),
                "features_json": r.get("features_json"),
            }
            for r in pool_rows
        ]
        heads = _predict_heads_for_pool(art, enrichment)
        if not heads:
            if verbose:
                print(f"[skip] {e.slate_date}: head empty")
            continue

        candidates = _counterfactual_candidates(pool_rows, heads, overlay, max_single_boost)
        chosen = _pick_five(candidates, boost_sum_cap)
        if len(chosen) < 5:
            if verbose:
                print(f"[skip] {e.slate_date}: only {len(chosen)} eligible under caps")
            continue

        results.append(_score_counterfactual(e, chosen, labels))
    return results


def _print_counterfactual(overlay: str, rows: list[dict]) -> None:
    print()
    print(f"{'=' * 78}")
    print(f"COUNTERFACTUAL: overlay = {overlay!r}")
    print(f"{'=' * 78}")
    if not rows:
        print("no slates scored (missing head predictions or team-cap infeasible)")
        return
    print(f"{'slate':<12}{'old':>7}{'new':>7}{'delta':>8}{'gap→':>8}{'gap':>7}{'result':>12}")
    n_up = n_down = n_median = 0
    total_delta = 0.0
    for r in rows:
        gap_before = r["gap_before"]
        gap_after = r["gap_after"]
        if gap_after is not None and gap_after <= 0:
            n_median += 1
            tag = "BEAT_MED"
        elif r["delta"] > 0:
            tag = "up"
        elif r["delta"] < 0:
            tag = "down"
        else:
            tag = "flat"
        if r["delta"] > 0:
            n_up += 1
        elif r["delta"] < 0:
            n_down += 1
        total_delta += r["delta"]
        print(
            f"{r['slate']:<12}{r['old']:>7.1f}{r['new']:>7.1f}"
            f"{r['delta']:>+8.1f}{gap_before:>+8.1f}"
            f"{(gap_after if gap_after is not None else 0.0):>+7.1f}"
            f"{tag:>12}"
        )
    print()
    print(
        f"Aggregate: n={len(rows)}  up={n_up}  down={n_down}  "
        f"total_delta={total_delta:+.1f}  beat_top20_median={n_median}"
    )


def _ledger_inputs(
    eng: Engine, slate_date: str
) -> tuple[dict[int, tuple[float, float]], list[dict], list]:
    with eng.connect() as conn:
        labels = {
            int(row._mapping["platform_player_id"]): (
                float(row._mapping["card_boost"] or 0.0),
                float(row._mapping["real_score"] or 0.0),
            )
            for row in conn.execute(
                text(
                    "SELECT platform_player_id, card_boost, real_score "
                    "FROM slate_labels WHERE slate_date = :sd AND real_score IS NOT NULL"
                ),
                {"sd": slate_date},
            ).fetchall()
        }
        pool_rows = [
            dict(row._mapping)
            for row in conn.execute(
                text(
                    "SELECT player_id, name, team, position, card_boost, features_json "
                    "FROM job1_enrichment WHERE slate_date = :sd"
                ),
                {"sd": slate_date},
            ).fetchall()
        ]
        leaderboard = conn.execute(
            text(
                "SELECT contest_id, score FROM contest_leaderboards "
                "WHERE slate_date = :sd ORDER BY rank ASC LIMIT 20"
            ),
            {"sd": slate_date},
        ).fetchall()
    return labels, pool_rows, leaderboard


def _hydrate_picks(
    pids: list[int],
    labels: dict[int, tuple[float, float]],
    pool_rows: list[dict],
) -> tuple[list[PlayerLine], dict[int, PlayerLine]]:
    pool_index = build_pool_index(pool_rows)
    for pid, line in pool_index.items():
        if pid in labels:
            line.card_boost, line.real_score = labels[pid]

    picks: list[PlayerLine] = []
    for pid in pids:
        source = pool_index.get(pid)
        if source is None:
            boost, real_score = labels.get(pid, (0.0, 0.0))
            source = PlayerLine(pid, f"pid={pid}", "", "", boost, real_score)
        elif pid in labels:
            source.card_boost, source.real_score = labels[pid]
        picks.append(source)
    return picks, pool_index


def _swap_candidates(
    picks: list[PlayerLine], pool_index: dict[int, PlayerLine], our_score: float
) -> list[SwapCandidate]:
    candidates: list[SwapCandidate] = []
    pick_ids = {pick.pid for pick in picks}
    for slot, pick in enumerate(picks):
        for candidate_id, candidate in pool_index.items():
            if candidate_id in pick_ids or candidate.real_score <= 0:
                continue
            trial = picks.copy()
            trial[slot] = candidate
            gain = score_lineup(trial) - our_score
            if gain > 0:
                candidates.append(
                    SwapCandidate(
                        slot=slot,
                        pick=pick,
                        alt=candidate,
                        gain=gain,
                        category=categorize_swap(pick, candidate),
                    )
                )
    return sorted(candidates, key=lambda candidate: candidate.gain, reverse=True)


def _ledger_entry(row: object, eng: Engine, verbose: bool) -> SlateEntry | None:
    slate_date = row.slate_date  # type: ignore[attr-defined]
    raw_lineup = row.lineup  # type: ignore[attr-defined]
    lineup = raw_lineup if isinstance(raw_lineup, dict) else json.loads(raw_lineup)
    pids = [int(value) for value in (lineup.get("player_ids") or [])]
    if len(pids) != 5:
        if verbose:
            print(f"[skip] {slate_date}: frozen lineup has {len(pids)} players")
        return None

    labels, pool_rows, leaderboard = _ledger_inputs(eng, slate_date)
    if not leaderboard:
        if verbose:
            print(f"[skip] {slate_date}: no leaderboard rows")
        return None

    picks, pool_index = _hydrate_picks(pids, labels, pool_rows)
    our_score = score_lineup(picks)
    scores = [float(item._mapping["score"]) for item in leaderboard]
    median_score = statistics.median(scores)
    candidates = _swap_candidates(picks, pool_index, our_score)
    missing_labels = [pid for pid in pids if pid not in labels]
    if missing_labels and verbose:
        print(f"[note] {slate_date}: missing labels for {missing_labels}")
    return SlateEntry(
        slate_date=slate_date,
        contest_id=int(leaderboard[0]._mapping["contest_id"]),
        model_sha=str(row.model_sha),  # type: ignore[attr-defined]
        freeze_seq=int(row.freeze_seq),  # type: ignore[attr-defined]
        our_picks=picks,
        our_score=our_score,
        top20_median=median_score,
        top20_min=min(scores),
        winner_score=max(scores),
        delta_vs_median=median_score - our_score,
        n_captured=len(scores),
        n_pool_scored=sum(1 for player in pool_index.values() if player.real_score > 0),
        top_swap=candidates[0] if candidates else None,
        all_swaps_top5=candidates[:5],
    )


def build_ledger(limit: int, verbose: bool = False) -> list[SlateEntry]:
    eng = get_engine()
    ledger: list[SlateEntry] = []

    # Latest freeze per slate for the last `limit` slates that have a
    # captured leaderboard. LIMIT more than we need in case some slates
    # have partial data.
    slates_q = text(
        """
        SELECT DISTINCT ON (f.slate_date)
            f.slate_date::text AS slate_date,
            f.model_sha,
            f.freeze_seq,
            f.lineup
        FROM frozen_lineups f
        JOIN contest_leaderboards cl ON cl.slate_date = f.slate_date::text
        ORDER BY f.slate_date DESC, f.freeze_seq DESC
        LIMIT :n
        """
    )
    with eng.connect() as conn:
        rows = conn.execute(slates_q, {"n": limit}).fetchall()

    for row in rows:
        entry = _ledger_entry(row, eng, verbose)
        if entry is not None:
            ledger.append(entry)

    return ledger


def print_table(ledger: list[SlateEntry]) -> None:
    if not ledger:
        print("no finalized slates found")
        return
    print(
        f"{'slate':<12} {'ours':>7} {'med':>7} {'delta':>7} "
        f"{'top_swap':>9} {'category':<20} {'alt_name':<24}"
    )
    print("-" * 100)
    for e in ledger:
        med = f"{e.top20_median:.1f}" if e.top20_median is not None else "-"
        delta = f"{e.delta_vs_median:+.1f}" if e.delta_vs_median is not None else "-"
        if e.top_swap:
            swap_gain = f"{e.top_swap.gain:+.1f}"
            cat = e.top_swap.category
            alt_name = (e.top_swap.alt.name or f"pid={e.top_swap.alt.pid}")[:24]
        else:
            swap_gain = "-"
            cat = "-"
            alt_name = "-"
        print(
            f"{e.slate_date:<12} {e.our_score:>7.1f} {med:>7} {delta:>7} "
            f"{swap_gain:>9} {cat:<20} {alt_name:<24}"
        )

    # Aggregate view: how often does each category top the ledger?
    from collections import Counter

    cats = Counter((e.top_swap.category if e.top_swap else "no_swap") for e in ledger)
    print()
    print(f"Category distribution across {len(ledger)} slates (top swap only):")
    for cat, n in cats.most_common():
        print(f"  {cat:<20} {n:>3} ({n / len(ledger):.0%})")

    # Aggregate loss magnitude by category (sum of gains, capped at that
    # slate's actual delta_vs_median so we don't overclaim beyond what
    # winning would have required).
    per_cat_gain: dict[str, float] = {}
    for e in ledger:
        if not e.top_swap or e.delta_vs_median is None:
            continue
        # Realized loss captured by fixing THIS one swap (bounded above by
        # the actual gap to median so we don't credit imaginary points).
        realized = min(e.top_swap.gain, max(e.delta_vs_median, 0.0))
        if realized <= 0:
            continue
        per_cat_gain[e.top_swap.category] = per_cat_gain.get(e.top_swap.category, 0.0) + realized
    if per_cat_gain:
        print()
        print("Realized loss addressable by top-1 swap, by category:")
        for cat, g in sorted(per_cat_gain.items(), key=lambda kv: -kv[1]):
            print(f"  {cat:<20} {g:>7.1f} pts across slates")

    # Median finish placement: how much of the ledger sits above / below
    # the top-20 median?
    beat_med = sum(
        1 for e in ledger if e.top20_median is not None and e.our_score >= e.top20_median
    )
    cracked = sum(1 for e in ledger if e.top20_min is not None and e.our_score >= e.top20_min)
    print()
    print(
        f"Beat top-20 median: {beat_med}/{len(ledger)}   "
        f"Cracked top-20 (>= min captured): {cracked}/{len(ledger)}"
    )


def write_csv(ledger: list[SlateEntry], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "slate_date",
                "contest_id",
                "model_sha",
                "freeze_seq",
                "our_score",
                "top20_median",
                "top20_min",
                "winner_score",
                "delta_vs_median",
                "n_captured",
                "n_pool_scored",
                "our_pids",
                "our_scores",
                "our_boosts",
                "top_swap_slot",
                "top_swap_gain",
                "top_swap_category",
                "top_swap_pick_name",
                "top_swap_alt_name",
                "top_swap_pick_boost",
                "top_swap_alt_boost",
                "top_swap_pick_rs",
                "top_swap_alt_rs",
            ]
        )
        for e in ledger:
            ts = e.top_swap
            w.writerow(
                [
                    e.slate_date,
                    e.contest_id,
                    e.model_sha,
                    e.freeze_seq,
                    f"{e.our_score:.2f}",
                    "" if e.top20_median is None else f"{e.top20_median:.2f}",
                    "" if e.top20_min is None else f"{e.top20_min:.2f}",
                    "" if e.winner_score is None else f"{e.winner_score:.2f}",
                    "" if e.delta_vs_median is None else f"{e.delta_vs_median:.2f}",
                    e.n_captured,
                    e.n_pool_scored,
                    ";".join(str(p.pid) for p in e.our_picks),
                    ";".join(f"{p.real_score:.1f}" for p in e.our_picks),
                    ";".join(f"{p.card_boost:.2f}" for p in e.our_picks),
                    "" if ts is None else ts.slot,
                    "" if ts is None else f"{ts.gain:.2f}",
                    "" if ts is None else ts.category,
                    "" if ts is None else ts.pick.name,
                    "" if ts is None else ts.alt.name,
                    "" if ts is None else f"{ts.pick.card_boost:.2f}",
                    "" if ts is None else f"{ts.alt.card_boost:.2f}",
                    "" if ts is None else f"{ts.pick.real_score:.1f}",
                    "" if ts is None else f"{ts.alt.real_score:.1f}",
                ]
            )


def main() -> int:
    ap = argparse.ArgumentParser(description="Per-slate loss ledger.")
    ap.add_argument("--limit", type=int, default=20, help="Number of slates.")
    ap.add_argument("--csv", type=str, default=None, help="Optional CSV output path.")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument(
        "--counterfactual",
        choices=("starter-fade", "boost-lift", "both", "starter-min-lift", "floor-tilt", "suite"),
        default=None,
        help=(
            "Re-pick top-5 for each slate under a hypothetical picker knob "
            "overlay and report per-slate deltas. See "
            "scripts/calibrate_starter_and_boost.py for how the multipliers "
            "were derived."
        ),
    )
    args = ap.parse_args()
    ledger = build_ledger(args.limit, verbose=args.verbose)
    print_table(ledger)
    if args.counterfactual:
        rows = _run_counterfactual(ledger, args.counterfactual, verbose=args.verbose)
        _print_counterfactual(args.counterfactual, rows)
        # Pure ship effect: rerun with the overlay off (baseline top-5 under
        # the same caps) and diff. Isolates the knob change from the picker's
        # guardrails, which can otherwise dominate the counterfactual signal.
        baseline_rows = _run_counterfactual(ledger, _OFF_OVERLAY, verbose=args.verbose)
        by_slate = {r["slate"]: r for r in baseline_rows}
        print()
        print("=" * 78)
        print("SHIP EFFECT: overlay ON vs overlay OFF (same guardrails)")
        print("=" * 78)
        print(
            f"{'slate':<12}{'off_new':>9}{'on_new':>8}{'ship_delta':>12}{'gap_off':>9}{'gap_on':>8}"
        )
        n_up = n_down = 0
        total = 0.0
        for r in rows:
            base = by_slate.get(r["slate"])
            if base is None:
                continue
            ship_delta = r["new"] - base["new"]
            gap_off = base["gap_after"] if base["gap_after"] is not None else 0.0
            gap_on = r["gap_after"] if r["gap_after"] is not None else 0.0
            if ship_delta > 0.1:
                n_up += 1
            elif ship_delta < -0.1:
                n_down += 1
            total += ship_delta
            print(
                f"{r['slate']:<12}{base['new']:>9.1f}{r['new']:>8.1f}"
                f"{ship_delta:>+12.1f}{gap_off:>+9.1f}{gap_on:>+8.1f}"
            )
        print()
        print(f"ship_effect: up={n_up}  down={n_down}  total_delta={total:+.1f}")
    if args.csv:
        out_path = Path(args.csv)
        if not out_path.is_absolute():
            out_path = _REPO_ROOT / out_path
        write_csv(ledger, out_path)
        print(f"\ncsv: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
