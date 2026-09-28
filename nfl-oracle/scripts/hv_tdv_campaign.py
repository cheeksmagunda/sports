#!/usr/bin/env python3
"""Shared-fit Highest-value / Total-value campaign on Corpus C (#603).

Observation only. Compares identity vs boost 0.75, max-1 defender, max-1
kicker, and slot-by-mean, plus cold-start chalk on the visible pool versus
the full participant roster of the contest's games. Does not change Railway.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from nfl_oracle.contests.parse import iter_contests
from nfl_oracle.contests.store import ContestStore
from nfl_oracle.recommendations.optimizer import OptimizerConfig
from nfl_oracle.recommendations.picker_knobs import PickerKnobs
from nfl_oracle.replay.contest_pool_replay import (
    ContestPool,
    ContestPoolResult,
    ReplaySetting,
    replay_contest_pools_setting_sweep,
    summarize,
)
from nfl_oracle.replay.production_backtest_cli import (
    add_fit_config_args,
    fit_config_from_args,
    load_backtest_inputs,
)
from nfl_oracle.replay.slate_regime import OPERATOR_REGIMES


def _pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{100.0 * value:.1f}%"


def _num(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def live_base(**overrides: object) -> OptimizerConfig:
    """Serving-shaped max_value construction. Caps and slot order are overrides."""

    payload: dict[str, object] = {
        "simulations": 100,
        "min_distinct_teams": 1,
        "min_distinct_games": 1,
        "profile": "max_value",
        "upside_weight": 0.15,
        "field_weight": 0.10,
        # Research arms start uncapped / joint; overrides flip one lever.
        "max_defenders": 0,
        "max_kickers": 0,
        "slot_by_mean": False,
    }
    payload.update(overrides)
    return OptimizerConfig(**payload)  # type: ignore[arg-type]


def visible_settings() -> tuple[ReplaySetting, ...]:
    """Full cross of the requested levers, plus the historical blend ladder."""

    settings: list[ReplaySetting] = []
    blends = ((0.0, "identity"), (0.75, "boost_0.75"))
    for blend, blend_name in blends:
        picker = PickerKnobs(
            boost_rank_blend=blend,
            profile=blend_name,
        )
        for defenders in (0, 1):
            for kickers in (0, 1):
                for slot_by_mean in (False, True):
                    def_label = "any" if defenders == 0 else str(defenders)
                    k_label = "any" if kickers == 0 else str(kickers)
                    slot_label = "mean" if slot_by_mean else "joint"
                    name = f"{blend_name}_def{def_label}_k{k_label}_slot{slot_label}"
                    settings.append(
                        ReplaySetting(
                            name=name,
                            picker=picker,
                            optimizer=live_base(
                                max_defenders=defenders,
                                max_kickers=kickers,
                                slot_by_mean=slot_by_mean,
                            ),
                        )
                    )
    extras = (
        PickerKnobs(boost_rank_blend=0.25, profile="boost_0.25"),
        PickerKnobs(boost_rank_blend=0.50, profile="boost_0.50"),
        PickerKnobs(position_calibration=1.0, profile="pos_1.0"),
        PickerKnobs(
            boost_rank_blend=0.35,
            position_calibration=0.5,
            profile="boost_0.35_pos_0.5",
        ),
    )
    for picker in extras:
        settings.append(
            ReplaySetting(
                name=f"{picker.profile}_defany_kany_slotjoint",
                picker=picker,
                optimizer=live_base(),
            )
        )
    return tuple(settings)


def chalk_settings() -> tuple[ReplaySetting, ...]:
    """Identity and live blend on each pool scope, caps off, joint slots."""

    out = []
    for blend, blend_name in ((0.0, "identity"), (0.75, "boost_0.75")):
        out.append(
            ReplaySetting(
                name=blend_name,
                picker=PickerKnobs(boost_rank_blend=blend, profile=blend_name),
                optimizer=live_base(),
            )
        )
    return tuple(out)


def _arm_row(name: str, results: tuple[ContestPoolResult, ...]) -> dict[str, object]:
    summary = summarize(results)
    cold_picks = [r.cold_start_picks for r in results]
    cold_candidates = [r.cold_start_candidates for r in results]
    priors = [r.mean_pick_prior_games for r in results if r.mean_pick_prior_games is not None]
    hv_hits = [r.hv_board_hits for r in results if r.hv_board_hits is not None]
    hv_capture = [r.hv_board_capture for r in results if r.hv_board_capture is not None]
    return {
        "name": name,
        "n": summary.all.n_contests,
        "mean_hv_board_hits": (sum(hv_hits) / len(hv_hits)) if hv_hits else None,
        "mean_hv_board_capture": (sum(hv_capture) / len(hv_capture)) if hv_capture else None,
        "hv_board_n": len(hv_hits),
        "mean_capture": summary.all.mean_capture_ratio,
        "median_capture": summary.all.median_capture_ratio,
        "mean_ordered_capture": summary.all.mean_ordered_capture_ratio,
        "mean_winner_capture": summary.all.mean_winner_capture_ratio,
        "mean_naive_capture": summary.all.mean_naive_capture_ratio,
        "contests_beating_winner": summary.all.contests_beating_winner,
        "zero_boost_n": summary.zero_boost.n_contests,
        "zero_boost_mean": summary.zero_boost.mean_capture_ratio,
        "boosted_n": summary.boosted.n_contests,
        "boosted_mean": summary.boosted.mean_capture_ratio,
        "mean_pick_prior_games": (sum(priors) / len(priors)) if priors else None,
        "mean_cold_start_picks": (sum(cold_picks) / len(cold_picks)) if cold_picks else None,
        "mean_cold_start_candidates": (
            (sum(cold_candidates) / len(cold_candidates)) if cold_candidates else None
        ),
    }


def _markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def render_report(payload: dict[str, object]) -> str:
    visible = payload["visible"]
    assert isinstance(visible, dict)
    chalk = payload["contest_games"]
    assert isinstance(chalk, dict)
    arms = visible["arms"]
    assert isinstance(arms, list)
    by_name = {str(arm["name"]): arm for arm in arms if isinstance(arm, dict)}

    def cell(name: str) -> list[str]:
        arm = by_name[name]
        return [
            name,
            str(arm["n"]),
            _num(arm["mean_hv_board_hits"]),  # type: ignore[arg-type]
            _pct(arm["mean_hv_board_capture"]),  # type: ignore[arg-type]
            str(arm["hv_board_n"]),
            _num(arm["mean_cold_start_picks"]),  # type: ignore[arg-type]
        ]

    headers = [
        "setting",
        "n",
        "HV board hits",
        "HV board Value",
        "boards scored",
        "cold-start picks",
    ]
    focus = [
        "identity_defany_kany_slotjoint",
        "boost_0.75_defany_kany_slotjoint",
        "boost_0.75_def1_kany_slotjoint",
        "boost_0.75_defany_k1_slotjoint",
        "boost_0.75_def1_k1_slotjoint",
        "boost_0.75_defany_kany_slotmean",
        "identity_defany_kany_slotmean",
        "boost_0.25_defany_kany_slotjoint",
        "boost_0.50_defany_kany_slotjoint",
        "pos_1.0_defany_kany_slotjoint",
    ]
    ranked = sorted(
        (arm for arm in arms if isinstance(arm, dict)),
        key=lambda arm: (
            -(
                arm["mean_hv_board_hits"]
                if isinstance(arm["mean_hv_board_hits"], int | float)
                else -1
            ),
            -(
                arm["mean_hv_board_capture"]
                if isinstance(arm["mean_hv_board_capture"], int | float)
                else -1
            ),
            str(arm["name"]),
        ),
    )
    chalk_arms = chalk["arms"]
    assert isinstance(chalk_arms, list)
    chalk_rows = []
    for arm in chalk_arms:
        if not isinstance(arm, dict):
            continue
        chalk_rows.append(
            [
                str(arm["name"]) + " contest_games",
                str(arm["n"]),
                _num(arm["mean_hv_board_hits"]),  # type: ignore[arg-type]
                _pct(arm["mean_hv_board_capture"]),  # type: ignore[arg-type]
                str(arm["hv_board_n"]),
                _num(arm["mean_cold_start_picks"]),  # type: ignore[arg-type]
            ]
        )
    visible_chalk_rows = []
    for name in ("identity_defany_kany_slotjoint", "boost_0.75_defany_kany_slotjoint"):
        arm = by_name[name]
        visible_chalk_rows.append(
            [
                name.removesuffix("_defany_kany_slotjoint") + " visible",
                str(arm["n"]),
                _num(arm["mean_hv_board_hits"]),  # type: ignore[arg-type]
                _pct(arm["mean_hv_board_capture"]),  # type: ignore[arg-type]
                str(arm["hv_board_n"]),
                _num(arm["mean_cold_start_picks"]),  # type: ignore[arg-type]
            ]
        )
    best = ranked[0] if ranked else None
    lines = [
        "# NFL Highest-value / Total-value campaign",
        "",
        f"Issue #{payload['issue']}. Generated {payload['finished_at']}.",
        "",
        "Success metric is the Highest-value / Total-value board: mean hits",
        "in the top 5 of `highestBoostedValuePlayers`, and the share of that",
        "board's Value total those hits carry. Hindsight capture and win",
        "counts are not the decision.",
        "",
        "Under `score = value * (slot + boost)`, a player's boost does not",
        "change which slot is optimal for a fixed five: the joint assignment",
        "already places higher projected values in higher slots. `slot_by_mean`",
        "diverges only when `Projection.mean` and the sample mean used by the",
        "slot scores disagree, or when a beam lineup was not re-sorted.",
        "",
        "Construction base matches live serve: `NFL_OPTIMIZER_PROFILE=max_value`",
        "(diversity floor 1/1), upside weight 0.15, field weight 0.10,",
        "simulations 100, weekly retrain, compact residual samples.",
        "Caps default off. Slot order defaults to the joint assignment.",
        "",
        "## Commands",
        "",
        "```sh",
        str(payload["command"]),
        "```",
        "",
        "## Focused comparison",
        "",
        _markdown_table(headers, [cell(name) for name in focus if name in by_name]),
        "",
        "## Ranked by HV/TDV board hits",
        "",
        _markdown_table(
            headers,
            [cell(str(arm["name"])) for arm in ranked if isinstance(arm, dict)],
        ),
        "",
        "## Full roster vs visible pool, same HV/TDV board",
        "",
        "Both scopes are scored against the contest Highest-value board.",
        "Visible pool is the contest's draft-stats players. Contest-game",
        "roster is every Corpus G participant on those games. Cold-start",
        "means zero Corpus G rows for that player strictly before the slate",
        "cutoff. Contest-game rows are postgame participants, so availability",
        "is generous versus a true pregame roster.",
        "",
        _markdown_table(
            [
                "arm",
                "n",
                "HV board hits",
                "HV board Value",
                "boards scored",
                "cold-start picks",
            ],
            visible_chalk_rows + chalk_rows,
        ),
        "",
    ]
    if isinstance(best, dict):
        lines.extend(
            [
                "## Top arm on this run",
                "",
                f"`{best['name']}` mean HV board hits "
                f"{_num(best['mean_hv_board_hits'])} "  # type: ignore[arg-type]
                f"Value capture {_pct(best['mean_hv_board_capture'])} "  # type: ignore[arg-type]
                f"on n={best['n']}.",
                "",
            ]
        )
    regimes = visible.get("regimes") if isinstance(visible, dict) else None
    if isinstance(regimes, dict):
        lines.extend(
            [
                "## Split by slate regime",
                "",
                "Sunday multi-game is not pooled with TNF, SNF, or MNF.",
                "A regime with n=0 was not scored. Do not copy another",
                "regime's capture into it.",
                "",
            ]
        )
        split_headers = ["regime", "setting", "n", "HV board hits", "HV board Value"]
        split_rows: list[list[str]] = []
        focus_regimes = (
            "sunday_multi",
            "one_night_tnf",
            "one_night_snf",
            "one_night_mnf",
        )
        focus_settings = (
            "identity_defany_kany_slotjoint",
            "boost_0.75_defany_kany_slotjoint",
            "boost_0.75_def1_k1_slotjoint",
        )
        for regime in focus_regimes:
            arms = regimes.get(regime)
            if not isinstance(arms, list):
                continue
            by_name = {str(arm["name"]): arm for arm in arms if isinstance(arm, dict)}
            for setting in focus_settings:
                arm = by_name.get(setting)
                if not isinstance(arm, dict):
                    continue
                split_rows.append(
                    [
                        regime,
                        setting,
                        str(arm["n"]),
                        _num(arm["mean_hv_board_hits"]),  # type: ignore[arg-type]
                        _pct(arm["mean_hv_board_capture"]),  # type: ignore[arg-type]
                    ]
                )
        lines.append(_markdown_table(split_headers, split_rows))
        lines.append("")
    lines.append(f"Contests with field evidence loaded: {payload['contests_with_field_evidence']}.")
    lines.append("")
    return "\n".join(lines)


def _run_scope(
    name: str,
    settings: tuple[ReplaySetting, ...],
    *,
    inputs: object,
    contests: list,
    fold_of,
    fit_config,
    pool_scope: str,
) -> dict[str, object]:
    def progress(line: str) -> None:
        print(line, file=sys.stderr, flush=True)

    swept = replay_contest_pools_setting_sweep(
        inputs.enriched,  # type: ignore[attr-defined]
        contests,
        settings,
        fold_of=fold_of,
        team_keys=inputs.team_keys,  # type: ignore[attr-defined]
        fit_config=fit_config,
        pool_scope=pool_scope,
        progress=progress,
    )
    arms = []
    excluded = {}
    for setting in settings:
        results, reasons = swept[setting.name]
        arms.append(_arm_row(setting.name, results))
        excluded[setting.name] = reasons
    regimes: dict[str, list[dict[str, object]]] = {}
    for regime in OPERATOR_REGIMES:
        regime_arms = []
        for setting in settings:
            results, _reasons = swept[setting.name]
            subset = tuple(result for result in results if result.slate_regime == regime)
            regime_arms.append(_arm_row(setting.name, subset))
        regimes[regime] = regime_arms
    return {"scope": name, "arms": arms, "excluded": excluded, "regimes": regimes}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hv-tdv-campaign")
    parser.add_argument("--history-root", type=Path, default=Path("data/raw/corpus_g"))
    parser.add_argument("--contest-root", type=Path, default=Path("data/raw/corpus_c"))
    parser.add_argument("--context-snapshot", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    add_fit_config_args(parser)
    args = parser.parse_args(argv)
    command = " ".join(sys.argv)
    inputs = load_backtest_inputs(args.history_root, args.context_snapshot)
    contests = [
        contest
        for contest in iter_contests(ContestStore(args.contest_root), finalized_only=True)
        if contest.has_field_evidence
    ]
    if not contests:
        print("no finalized Corpus C contests with field evidence", file=sys.stderr)
        return 2
    week_of = inputs.week_of

    def fold_of(pool: ContestPool):
        return min(week_of[game_id] for game_id in pool.day_game_ids)

    started = datetime.now(UTC)
    fit_config = fit_config_from_args(args)
    visible = _run_scope(
        "visible",
        visible_settings(),
        inputs=inputs,
        contests=contests,
        fold_of=fold_of,
        fit_config=fit_config,
        pool_scope="visible",
    )
    contest_games = _run_scope(
        "contest_games",
        chalk_settings(),
        inputs=inputs,
        contests=contests,
        fold_of=fold_of,
        fit_config=fit_config,
        pool_scope="contest_games",
    )
    finished = datetime.now(UTC)
    payload: dict[str, object] = {
        "kind": "hv_tdv_campaign",
        "issue": 603,
        "command": command,
        "fit_config": fit_config.model_dump(mode="json"),
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "contests_with_field_evidence": len(contests),
        "history_rows": len(inputs.rows),
        "context_rows": inputs.context_rows,
        "context_evidence_mode": inputs.context_evidence_mode,
        "visible": visible,
        "contest_games": contest_games,
        "contest_entry": False,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    report = render_report(payload)
    args.report.write_text(report)
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
