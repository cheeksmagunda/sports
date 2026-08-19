"""Offline model lab: the one entry point for evaluating a change.

Reads the frozen snapshot written by ``scripts/snapshot_corpus.py``. Touches no
service, needs no credentials, and cannot write to production.

Two modes:

    baseline   Score our frozen history honestly and print the metric block.
               This is the number any change has to beat.

    variant    Re-run the production optimizer over the same slates with an
               OptimizeConfig override, score the resulting lineups with the
               SAME scorer, and print the per-slate delta.

Scoring uses ``wnba_oracle.eval.contest_score.committed_order_score``: realized
value applied to the slot order AS COMMITTED. That matters. The optimizer's
``picker.sample.lineup_score_samples`` re-sorts players by each Monte-Carlo
sample's realized value, handing the 2.0x slot to whoever spiked in that draw,
which is not something an entrant can do. ``scripts/loss_ledger.py`` had copied
that same hindsight sort into its evaluation, and was repointed at the honest
scorer on 2026-08-19. A backtest that shares the bug with the
code under test cannot see the bug, so this module refuses to import from
``wnba_oracle.picker`` for scoring and reports the hindsight number separately
and explicitly as an unreachable upper bound.

Regime warning: ``recent_minutes`` / ``per_min_rate`` are present in enrichment
on only a minority of slates (the stats.wnba.com fetch fails soft from Railway's
egress). ``--regime with|without|all`` segments on that, because pooling across
the boundary mixes two different serving conditions.

Usage:
    uv run --extra dev python scripts/lab.py baseline
    uv run --extra dev python scripts/lab.py baseline --regime with --last 40
    uv run --extra dev python scripts/lab.py variant --set boost_sum_cap=0 --last 20
    uv run --extra dev python scripts/lab.py variant --set ceiling_tilt_slots=False
"""

from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from wnba_oracle.eval.contest_score import (  # noqa: E402
    DEFAULT_SLOT_BASES,
    committed_order_score,
    hindsight_max_score,
)
from wnba_oracle.predict.scoring import box_to_real_score  # noqa: E402

SNAPSHOT = REPO_ROOT / "data" / "snapshot"


# --------------------------------------------------------------------------
# snapshot loading
# --------------------------------------------------------------------------
def _load(name: str) -> pd.DataFrame:
    path = SNAPSHOT / f"{name}.parquet"
    if not path.exists():
        raise SystemExit(
            f"missing {path}. Run: uv run --extra dev python scripts/snapshot_corpus.py"
        )
    return pd.read_parquet(path)


def _jload(raw: object) -> object:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    return raw


def _fold(name: str) -> str:
    """Fold a display name to a join key. Real Sports renders 'N. Cloud';
    wnba_game_logs carries 'Natasha Cloud'. Match on last name + first initial."""
    parts = str(name or "").replace(".", "").split()
    if len(parts) < 2:
        return str(name or "").strip().lower()
    return f"{parts[0][:1]}|{parts[-1]}".lower()


@dataclass
class ValueBook:
    """Realized real_score lookups, most authoritative source first."""

    by_pid: dict[tuple[str, int], float]
    by_name: dict[tuple[str, str], float]

    def get(self, slate: str, pid: int | None, name: str | None) -> float | None:
        if pid is not None:
            v = self.by_pid.get((slate, int(pid)))
            if v is not None:
                return v
        if name:
            return self.by_name.get((slate, _fold(name)))
        return None


def build_value_book() -> ValueBook:
    """Realized value per (slate, player).

    Priority: leaderboard JSONB (the platform's own exact ``value``), then
    slate_labels, then wnba_game_logs reconstructed via box_to_real_score.
    """
    by_pid: dict[tuple[str, int], float] = {}
    by_name: dict[tuple[str, str], float] = {}

    for _, r in _load("contest_leaderboards").iterrows():
        for p in _jload(r["lineup"]) or []:
            try:
                sd = str(r["slate_date"])
                by_pid[(sd, int(p["playerId"]))] = float(p["value"])
                by_name.setdefault((sd, _fold(p.get("displayName"))), float(p["value"]))
            except (KeyError, TypeError, ValueError):
                continue

    for _, r in _load("slate_labels").iterrows():
        if pd.isna(r["real_score"]):
            continue
        by_name.setdefault((str(r["slate_date"]), _fold(r["display_name"])), float(r["real_score"]))

    gl = _load("wnba_game_logs")
    for _, r in gl.iterrows():
        box = {k: (0.0 if pd.isna(r.get(k)) else float(r.get(k))) for k in
               ("pts", "reb", "oreb", "dreb", "ast", "stl", "blk", "tov",
                "fgm", "fga", "fg3m", "ftm", "fta")}
        by_name.setdefault(
            (str(r["game_date"]), _fold(r["player_name"])), box_to_real_score(box)
        )
    return ValueBook(by_pid, by_name)


# --------------------------------------------------------------------------
# per-slate evaluation
# --------------------------------------------------------------------------
@dataclass
class SlateRow:
    slate: str
    ours: float
    ours_hindsight: float
    dnp_picks: int
    winner: float
    rank20: float
    top5_recovered: int
    minutes_regime: bool

    @property
    def ratio(self) -> float:
        return self.ours / self.winner if self.winner else float("nan")

    @property
    def slot_headroom(self) -> float:
        return self.ours_hindsight - self.ours


def _slate_top_values(book: ValueBook, slate: str, pool_names: list[str]) -> list[float]:
    vals = [book.get(slate, None, n) for n in pool_names]
    return sorted((v for v in vals if v is not None), reverse=True)


def latest_freeze_per_slate(frozen: pd.DataFrame) -> pd.DataFrame:
    """One row per slate: the last freeze written before lock.

    ``freeze_seq`` is NOT a per-slate sequence -- every row in the corpus carries
    ``freeze_seq == 1``, including the D75 23:00 UTC late re-freeze, which lands
    as a second ``frozen_via='job2_late_refreeze'`` row for the same slate. On
    2026-06-07 that gave two lineups with no player in common. Filtering on
    ``freeze_seq == 1`` therefore scores the superseded lineup AND double-counts
    the slate. The entry that actually stood at lock is the latest ``frozen_at``.
    """
    ordered = frozen.sort_values(["slate_date", "frozen_at"])
    # drop_duplicates, not groupby().last(): groupby takes the last NON-NULL
    # value per column independently, which would splice a null-free column from
    # the superseded row into the surviving one. This keeps whole rows.
    return ordered.drop_duplicates(subset="slate_date", keep="last")


def evaluate_frozen(
    regime_filter: str = "all", last: int | None = None
) -> tuple[list[SlateRow], list[tuple[str, str]]]:
    """Score every evaluable frozen lineup. Returns ``(rows, dropped)``.

    A pick with no entry in any value source is scored 0, not dropped: on a slate
    whose realized data we DO have, "absent from leaderboard, slate_labels and
    game logs" means the player did not play, and a DNP really is worth zero.
    Those are the selection disasters, so excluding them would inflate the
    baseline exactly where it should hurt. A slate whose realized data we do NOT
    have (the 2026-05-26..05-30 enrichment rows carry empty ``name`` strings and
    resolve nothing) is unevaluable and is dropped with its reason reported,
    never silently.
    """
    book = build_value_book()
    frozen = latest_freeze_per_slate(_load("frozen_lineups"))
    lb = _load("contest_leaderboards")
    regime = _load("slate_regime").set_index("slate_date")
    enrich = _load("job1_enrichment")

    lb_by_slate: dict[str, list[tuple[int, float]]] = {}
    for _, r in lb.iterrows():
        lb_by_slate.setdefault(str(r["slate_date"]), []).append((int(r["rank"]), float(r["score"])))
    pool_by_slate: dict[str, list[str]] = {}
    for sd, grp in enrich.groupby("slate_date"):
        pool_by_slate[str(sd)] = [str(x) for x in grp["name"].tolist()]

    rows: list[SlateRow] = []
    dropped: list[tuple[str, str]] = []
    for _, fr in frozen.sort_values("slate_date").iterrows():
        slate = str(fr["slate_date"])
        board = sorted(lb_by_slate.get(slate, []))
        if not board:
            dropped.append((slate, "no leaderboard"))
            continue
        lineup = _jload(fr["lineup"]) or {}
        picks = lineup.get("per_player") or []
        if len(picks) != len(DEFAULT_SLOT_BASES):
            dropped.append((slate, f"{len(picks)} picks, expected {len(DEFAULT_SLOT_BASES)}"))
            continue

        has_minutes = bool(regime["minutes_features_present"].get(slate, False))
        if regime_filter == "with" and not has_minutes:
            continue
        if regime_filter == "without" and has_minutes:
            continue

        top5_all = _slate_top_values(book, slate, pool_by_slate.get(slate, []))
        if not top5_all:
            dropped.append((slate, "no realized values resolve for this slate"))
            continue

        values: list[float] = []
        boosts: list[float] = []
        dnp = 0
        for p in picks:
            v = book.get(slate, p.get("player_id"), p.get("display_name"))
            if v is None:
                v = 0.0
                dnp += 1
            values.append(v)
            boosts.append(float(p.get("card_boost") or 0.0))

        cutoff = min(top5_all[:5])
        recovered = sum(1 for v in values if v >= cutoff and v > 0)

        rows.append(
            SlateRow(
                slate=slate,
                ours=committed_order_score(values, boosts),
                ours_hindsight=hindsight_max_score(values, boosts),
                dnp_picks=dnp,
                winner=board[0][1],
                rank20=board[-1][1],
                top5_recovered=recovered,
                minutes_regime=has_minutes,
            )
        )
    if last:
        rows = rows[-last:]
    return rows, dropped


def report(rows: list[SlateRow], dropped: list[tuple[str, str]], title: str) -> None:
    print(f"\n=== {title} ===")
    print(f"slates scored: {len(rows)}; dropped as unevaluable: {len(dropped)}")
    for slate, why in dropped:
        print(f"  dropped {slate}: {why}")
    if not rows:
        print("nothing to report")
        return
    print(
        f"\n{'slate':12s} {'ours':>7s} {'hindsght':>8s} {'headrm':>6s} "
        f"{'winner':>7s} {'rank20':>7s} {'ratio':>6s} {'top5':>4s} {'dnp':>3s} {'min':>4s}"
    )
    for r in rows:
        print(
            f"{r.slate:12s} {r.ours:7.2f} {r.ours_hindsight:8.2f} {r.slot_headroom:6.2f} "
            f"{r.winner:7.2f} {r.rank20:7.2f} {r.ratio:6.3f} {r.top5_recovered:4d} "
            f"{r.dnp_picks:3d} {'Y' if r.minutes_regime else 'n':>4s}"
        )
    print("\n--- aggregate (committed slot order, the achievable metric) ---")
    print(f"  mean ours            {st.mean(r.ours for r in rows):7.2f}")
    print(f"  mean winner          {st.mean(r.winner for r in rows):7.2f}")
    print(f"  mean rank-20 cutoff  {st.mean(r.rank20 for r in rows):7.2f}")
    print(f"  mean ours/winner     {st.mean(r.ratio for r in rows):7.3f}")
    print(f"  reached top-20 board {sum(1 for r in rows if r.ours >= r.rank20)} of {len(rows)}")
    print(f"  mean top-5 recovered {st.mean(r.top5_recovered for r in rows):7.2f} of 5")
    print(
        f"  slates with a DNP pick {sum(1 for r in rows if r.dnp_picks):5d}"
        f"   ({sum(r.dnp_picks for r in rows)} picks scored 0 for not playing)"
    )
    print(
        f"  mean slot headroom   {st.mean(r.slot_headroom for r in rows):7.2f}"
        "   (points a perfect ex-post slot order would have added; NOT achievable)"
    )
    print(
        "\n  NOTE the top-20 board is the top ~20 of roughly 7800 entries (~0.26th pct),\n"
        "  not the 20th-percentile cash line. We only observe the top 20 ranks, so this\n"
        "  cannot be read as a cash rate."
    )


# --------------------------------------------------------------------------
# variant mode
# --------------------------------------------------------------------------
def _coerce(v: str) -> object:
    low = v.lower()
    if low in ("true", "false"):
        return low == "true"
    try:
        return int(v) if "." not in v else float(v)
    except ValueError:
        return v


def arm_model_artifact() -> str:
    """Point Settings at the local model artifact and confirm it loads.

    The artifact SHA is Railway-only config, so a bare local run leaves
    ``WNBA_ORACLE_MODEL_ARTIFACT_SHA`` empty and ``_build_specs`` falls back to
    the heuristic predictor for every player: ``predictor_mix`` logs
    ``n_head_predicted=0 n_heuristic_fallback=<pool size>``. It still produces
    lineups, so the failure is silent, and a variant measured that way describes
    a model production does not run. Refuse to continue instead.

    Must be called before the first ``get_settings()``, which is lru_cached.
    """
    import os

    from wnba_oracle.common.settings import get_settings

    shas = sorted(SNAPSHOT.parent.parent.glob("models/*.sha256"))
    if not shas:
        raise SystemExit("no models/*.sha256 present; cannot replay the production predictor")
    sha = shas[-1].read_text().strip()
    os.environ["WNBA_ORACLE_MODEL_ARTIFACT_SHA"] = sha
    get_settings.cache_clear()

    from wnba_oracle.scheduler.job2 import _load_model_artifact

    if _load_model_artifact(sha) is None:
        raise SystemExit(f"model artifact {sha[:12]} did not load; refusing to score a fallback")
    return sha


def run_variant(overrides: dict[str, object], last: int | None) -> None:
    """Re-run the production optimizer under an OptimizeConfig override.

    Reuses ``job2._build_specs`` and ``picker.optimize_lineup`` directly so the
    variant path exercises production code rather than a reimplementation.

    SLOW. ``optimize_lineup`` defaults to n_samples=5000 over C(30,5) = 142,506
    candidate lineups, and each slate is optimized twice (base and variant), so
    budget minutes per slate and keep ``--last`` small.
    """
    from dataclasses import replace

    sha = arm_model_artifact()
    print(f"model artifact armed: {sha[:12]}")

    from wnba_oracle.picker.optimize import OptimizeConfig, optimize_lineup
    from wnba_oracle.picker.payout import default_curve_for_regime, load_curve_from_archive
    from wnba_oracle.scheduler.job2 import _build_specs

    book = build_value_book()
    enrich = _load("job1_enrichment")
    regime = _load("slate_regime").set_index("slate_date")
    lb = _load("contest_leaderboards")
    lb_by_slate: dict[str, list[tuple[int, float]]] = {}
    for _, r in lb.iterrows():
        lb_by_slate.setdefault(str(r["slate_date"]), []).append((int(r["rank"]), float(r["score"])))

    slates = sorted({str(s) for s in enrich["slate_date"].unique()} & set(lb_by_slate))
    if last:
        slates = slates[-last:]

    base_cfg = OptimizeConfig()
    unknown = [k for k in overrides if not hasattr(base_cfg, k)]
    if unknown:
        raise SystemExit(f"unknown OptimizeConfig field(s): {unknown}")
    var_cfg = replace(base_cfg, **overrides)

    print(f"\n=== VARIANT {overrides} over {len(slates)} slates ===")
    print(f"{'slate':12s} {'base':>7s} {'variant':>8s} {'delta':>7s} {'winner':>7s} {'min':>4s}")
    deltas: list[float] = []
    for slate in slates:
        rows = [
            {k: (_jload(v) if k == "features_json" else v) for k, v in r.items()}
            for r in enrich[enrich["slate_date"].astype(str) == slate].to_dict("records")
        ]
        try:
            samps, fields, _ = _build_specs(rows, slate_date=slate)
        except Exception as exc:
            print(f"{slate:12s}  spec build failed: {type(exc).__name__}: {exc}")
            continue
        if len(samps) < 5:
            continue

        # Same curve resolution job2 uses, so the variant is scored against the
        # payout structure that slate actually ran under.
        curve = load_curve_from_archive(slate) or default_curve_for_regime("top_20")
        scored: dict[str, float] = {}
        for label, cfg in (("base", base_cfg), ("variant", var_cfg)):
            rec = optimize_lineup(samps, fields, curve, cfg=cfg)
            by_pid = {int(s.player_id): s for s in samps}
            vals, boos = [], []
            for pid in rec.player_ids:
                spec = by_pid.get(int(pid))
                v = book.get(slate, int(pid), None)
                vals.append(v if v is not None else 0.0)
                boos.append(float(spec.boost) if spec else 0.0)
            scored[label] = committed_order_score(vals, boos)

        d = scored["variant"] - scored["base"]
        deltas.append(d)
        has_min = bool(regime["minutes_features_present"].get(slate, False))
        print(
            f"{slate:12s} {scored['base']:7.2f} {scored['variant']:8.2f} {d:+7.2f} "
            f"{sorted(lb_by_slate[slate])[0][1]:7.2f} {'Y' if has_min else 'n':>4s}",
            flush=True,
        )
    if deltas:
        wins = sum(1 for d in deltas if d > 0)
        print(f"\n  mean delta {st.mean(deltas):+.3f} over {len(deltas)} slates; "
              f"variant better on {wins}, worse on {sum(1 for d in deltas if d < 0)}")
        print("  Treat a small mean delta on a few dozen slates as noise. Check the sign\n"
              "  consistency and segment by the minutes regime before believing it.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="mode", required=True)
    b = sub.add_parser("baseline", help="score our frozen history honestly")
    b.add_argument("--regime", choices=["all", "with", "without"], default="all")
    b.add_argument("--last", type=int, default=None)
    v = sub.add_parser("variant", help="re-run the optimizer with an OptimizeConfig override")
    v.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    v.add_argument("--last", type=int, default=20)
    args = ap.parse_args()

    if args.mode == "baseline":
        rows, dropped = evaluate_frozen(args.regime, args.last)
        report(rows, dropped, f"BASELINE (regime={args.regime})")
        return 0

    overrides = {}
    for item in args.set:
        if "=" not in item:
            raise SystemExit(f"--set expects KEY=VALUE, got {item!r}")
        k, _, val = item.partition("=")
        overrides[k.strip()] = _coerce(val.strip())
    if not overrides:
        raise SystemExit("variant mode needs at least one --set KEY=VALUE")
    run_variant(overrides, args.last)
    return 0


if __name__ == "__main__":
    sys.exit(main())
