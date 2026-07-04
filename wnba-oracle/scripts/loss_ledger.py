"""Per-slate loss ledger: where our frozen lineup lost points, and why.

Answers "did we lose a slate we should have won, and would proposal X have
caught it?" for the last N finalized slates. Reads-only against prod
Postgres. No new tables; no cron. Run on demand before deciding what to
build next.

For each finalized slate (has a frozen lineup AND slate_labels for its
five picks AND a captured leaderboard):

  1. Compute our realized lineup score using the same rearrangement-inequality
     slot assignment as picker.sample.lineup_score_samples:
         final = sum_i real_score_i * (card_boost_i + slot_mult_j)
     with slot_mult in (2.0, 1.8, 1.6, 1.4, 1.2) assigned by real_score rank.

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

# Load .env so DATABASE_URL / DATABASE_PUBLIC_URL is available when the
# script runs outside the Claude Code session env. Same pattern as other
# on-demand scripts in this repo.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_ENV_PATH = _REPO_ROOT / ".env"
if _ENV_PATH.exists() and not os.environ.get("DATABASE_URL"):
    for _line in _ENV_PATH.read_text().splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _v = _line.split("=", 1)
        _v = _v.strip().strip('"').strip("'")
        if _k.strip() == "DATABASE_PUBLIC_URL" and _v and not os.environ.get("DATABASE_URL"):
            os.environ["DATABASE_URL"] = _v

from sqlalchemy import text  # noqa: E402

from wnba_oracle.db.engine import get_engine  # noqa: E402

SLOT_MULTIPLIERS = (2.0, 1.8, 1.6, 1.4, 1.2)


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
    """Contest score for a five-player lineup using rearrangement-inequality
    slot assignment. Matches picker.sample.lineup_score_samples."""
    if len(players) != 5:
        return 0.0
    sorted_by_rs = sorted(players, key=lambda p: p.real_score, reverse=True)
    total = 0.0
    for slot_idx, p in enumerate(sorted_by_rs):
        total += p.real_score * (p.card_boost + SLOT_MULTIPLIERS[slot_idx])
    return total


def categorize_swap(pick: PlayerLine, alt: PlayerLine) -> str:
    """Categorize why our lineup passed on `alt` in favor of `pick`.

    Priority order matches operator judgment: boost gaps are the easiest to
    audit, then starter signal, then prop signal, then generic model
    underrate. `unclassified` = alt looks equivalent on the surface, so
    the miss is likely in the head predictions themselves.
    """
    if alt.card_boost > pick.card_boost + 0.15:
        return "boost_underweight"
    alt_expected = bool(alt.is_starter) and (
        bool(alt.rotowire_confirmed) or bool(alt.is_starter)
    )
    pick_expected = bool(pick.is_starter) and (
        bool(pick.rotowire_confirmed) or bool(pick.is_starter)
    )
    if alt_expected and not pick_expected:
        return "starter_signal"
    if alt.prop_over_prob is not None and alt.prop_over_prob >= 0.60 and (
        pick.prop_over_prob is None or pick.prop_over_prob < alt.prop_over_prob - 0.05
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
                float(f["prop_points_line"])
                if f.get("prop_points_line") is not None
                else None
            ),
            recent_minutes=(
                float(f["recent_minutes"])
                if f.get("recent_minutes") is not None
                else None
            ),
            per_min_rate=(
                float(f["per_min_rate"])
                if f.get("per_min_rate") is not None
                else None
            ),
        )
        out[pid] = line
    return out


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
        sd = row.slate_date
        raw_lineup = row.lineup
        lineup_dict = raw_lineup if isinstance(raw_lineup, dict) else json.loads(raw_lineup)
        pids: list[int] = [int(x) for x in (lineup_dict.get("player_ids") or [])]
        if len(pids) != 5:
            if verbose:
                print(f"[skip] {sd}: frozen lineup has {len(pids)} players")
            continue

        with eng.connect() as conn:
            # Slate labels (realized real_score) for every player who
            # showed up in the pool - covers our picks + swap candidates.
            labels_q = text(
                """
                SELECT platform_player_id, card_boost, real_score
                FROM slate_labels
                WHERE slate_date = :sd AND real_score IS NOT NULL
                """
            )
            labels = {
                int(r._mapping["platform_player_id"]): (
                    float(r._mapping["card_boost"] or 0.0),
                    float(r._mapping["real_score"] or 0.0),
                )
                for r in conn.execute(labels_q, {"sd": sd}).fetchall()
            }

            # Pool at freeze from job1_enrichment.
            pool_q = text(
                """
                SELECT player_id, name, team, position, card_boost, features_json
                FROM job1_enrichment
                WHERE slate_date = :sd
                """
            )
            pool_rows = [dict(r._mapping) for r in conn.execute(pool_q, {"sd": sd}).fetchall()]

            # Captured top-20 scores + contest_id.
            lb_q = text(
                """
                SELECT contest_id, score
                FROM contest_leaderboards
                WHERE slate_date = :sd
                ORDER BY rank ASC
                LIMIT 20
                """
            )
            lb_rows = conn.execute(lb_q, {"sd": sd}).fetchall()

        if not lb_rows:
            if verbose:
                print(f"[skip] {sd}: no leaderboard rows")
            continue

        # Skip slates where any of our picks lacks a realized score - a
        # gap means the pick did not play; scoring it as zero is fine as
        # a lineup-total measurement, but our_score would understate what
        # the lineup meant to project. Include those slates but mark them.
        missing_labels = [pid for pid in pids if pid not in labels]

        pool_index = build_pool_index(pool_rows)
        # Fill realized real_score onto the pool index (drops pool players
        # who don't have a slate_labels row, e.g. they didn't play or were
        # never scored).
        for pid, line in list(pool_index.items()):
            if pid in labels:
                line.card_boost = labels[pid][0]  # authoritative post-lock boost
                line.real_score = labels[pid][1]

        # Build our five PlayerLines. Fall back to synthesized lines when
        # a pick is missing from the pool_index or from labels.
        our_picks: list[PlayerLine] = []
        for pid in pids:
            src = pool_index.get(pid)
            if src is None:
                # Not in enrichment: fabricate a stub so the loop keeps
                # going. Boost/real_score come from labels if present.
                boost, rs = labels.get(pid, (0.0, 0.0))
                src = PlayerLine(pid=pid, name=f"pid={pid}", team="", position="",
                                 card_boost=boost, real_score=rs)
            # Enforce realized score even if we found the pool line via
            # enrichment (the previous fill loop skipped missing labels).
            if pid in labels:
                src.card_boost = labels[pid][0]
                src.real_score = labels[pid][1]
            our_picks.append(src)

        our_score = score_lineup(our_picks)

        lb_scores = [float(r._mapping["score"]) for r in lb_rows]
        contest_id = int(lb_rows[0]._mapping["contest_id"]) if lb_rows else None
        top20_median = statistics.median(lb_scores) if lb_scores else None
        top20_min = min(lb_scores) if lb_scores else None
        winner_score = max(lb_scores) if lb_scores else None
        delta = (top20_median - our_score) if top20_median is not None else None

        # Swap-one exercise. For each slot, sweep every pool player with a
        # realized score, replace that slot, recompute lineup score. Track
        # the single best swap plus a top-5 leaderboard for the CSV.
        n_pool_scored = sum(1 for pl in pool_index.values() if pl.real_score > 0)
        candidates: list[SwapCandidate] = []
        our_pids_set = {p.pid for p in our_picks}
        for slot_idx, pick in enumerate(our_picks):
            for cand_pid, cand in pool_index.items():
                if cand_pid in our_pids_set:
                    continue
                if cand.real_score <= 0:  # didn't play or no label
                    continue
                trial = our_picks.copy()
                trial[slot_idx] = cand
                trial_score = score_lineup(trial)
                gain = trial_score - our_score
                if gain <= 0:
                    continue
                candidates.append(
                    SwapCandidate(
                        slot=slot_idx,
                        pick=pick,
                        alt=cand,
                        gain=gain,
                        category=categorize_swap(pick, cand),
                    )
                )

        candidates.sort(key=lambda c: c.gain, reverse=True)
        top_swap = candidates[0] if candidates else None
        top5 = candidates[:5]

        entry = SlateEntry(
            slate_date=sd,
            contest_id=contest_id,
            model_sha=str(row.model_sha),
            freeze_seq=int(row.freeze_seq),
            our_picks=our_picks,
            our_score=our_score,
            top20_median=top20_median,
            top20_min=top20_min,
            winner_score=winner_score,
            delta_vs_median=delta,
            n_captured=len(lb_scores),
            n_pool_scored=n_pool_scored,
            top_swap=top_swap,
            all_swaps_top5=top5,
        )
        if missing_labels and verbose:
            print(f"[note] {sd}: missing labels for {missing_labels}")
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
    cats = Counter(
        (e.top_swap.category if e.top_swap else "no_swap") for e in ledger
    )
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
    cracked = sum(
        1 for e in ledger if e.top20_min is not None and e.our_score >= e.top20_min
    )
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
                "slate_date", "contest_id", "model_sha", "freeze_seq",
                "our_score", "top20_median", "top20_min", "winner_score",
                "delta_vs_median", "n_captured", "n_pool_scored",
                "our_pids", "our_scores", "our_boosts",
                "top_swap_slot", "top_swap_gain", "top_swap_category",
                "top_swap_pick_name", "top_swap_alt_name",
                "top_swap_pick_boost", "top_swap_alt_boost",
                "top_swap_pick_rs", "top_swap_alt_rs",
            ]
        )
        for e in ledger:
            ts = e.top_swap
            w.writerow(
                [
                    e.slate_date, e.contest_id, e.model_sha, e.freeze_seq,
                    f"{e.our_score:.2f}",
                    "" if e.top20_median is None else f"{e.top20_median:.2f}",
                    "" if e.top20_min is None else f"{e.top20_min:.2f}",
                    "" if e.winner_score is None else f"{e.winner_score:.2f}",
                    "" if e.delta_vs_median is None else f"{e.delta_vs_median:.2f}",
                    e.n_captured, e.n_pool_scored,
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
    args = ap.parse_args()
    ledger = build_ledger(args.limit, verbose=args.verbose)
    print_table(ledger)
    if args.csv:
        out_path = Path(args.csv)
        if not out_path.is_absolute():
            out_path = _REPO_ROOT / out_path
        write_csv(ledger, out_path)
        print(f"\ncsv: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
