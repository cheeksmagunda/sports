#!/usr/bin/env python3
"""Score lineups against HV/TDV boards, split by Sunday and one-night.

Screenshot boards are Sunday. One-night contest days are counted from the
historical contest inventory joined to the nflverse schedule. Optimizer
overlap is reported only for boards that were actually scored. A Sunday
rate is never copied onto TNF, SNF, or MNF.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from nfl_oracle.calendar.schedule import load_schedules_csv
from nfl_oracle.replay.hv_board_overlap import (
    BoardRow,
    parse_draft_count,
    parse_slot,
    score_board,
)
from nfl_oracle.replay.slate_regime import (
    ONE_NIGHT_REGIMES,
    OPERATOR_REGIMES,
    SUNDAY_MULTI,
    regime_from_kickoffs,
)


def _load_board(path: Path) -> tuple[str, str, tuple[BoardRow, ...]]:
    payload = json.loads(path.read_text())
    rows = []
    for raw in payload["rows"]:
        rows.append(
            BoardRow(
                player_id=int(raw["player_id"]),
                name=str(raw["name"]),
                position=str(raw["position"]),
                team=str(raw["team"]),
                base=float(raw["base"]),
                boost=float(raw["boost"]),
                most_common_slot=parse_slot(str(raw["slot"])),
                draft_count=parse_draft_count(raw["drafts"]),
                displayed_value=float(raw["value"]),
            )
        )
    return str(payload["slate_date"]), str(payload["regime"]), tuple(rows)


def _inventory(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text())
    found: list[dict[str, object]] = []
    seen: set[int] = set()

    def walk(node: object) -> None:
        if isinstance(node, dict):
            sport = node.get("sport")
            day = node.get("day")
            contest_id = node.get("id", node.get("contestId"))
            if sport == "nfl" and isinstance(day, str) and isinstance(contest_id, int):
                if contest_id not in seen:
                    seen.add(contest_id)
                    found.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(payload)
    return found


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{100.0 * value:.1f}%"


def _num(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def _table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _aggregate(board_payloads: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    by_regime: dict[str, list[dict[str, object]]] = defaultdict(list)
    for board in board_payloads:
        by_regime[str(board["regime"])].append(board)
    out: dict[str, dict[str, object]] = {}
    for regime in OPERATOR_REGIMES:
        boards = by_regime.get(regime, [])
        policy_names: list[str] = []
        if boards:
            policies = boards[0]["policies"]
            assert isinstance(policies, list)
            policy_names = [str(item["name"]) for item in policies if isinstance(item, dict)]
        rows = []
        for name in policy_names:
            hv_hits: list[float] = []
            captures: list[float] = []
            for board in boards:
                policies = board["policies"]
                assert isinstance(policies, list)
                match = next(item for item in policies if item["name"] == name)
                assert isinstance(match, dict)
                hv_hits.append(float(match["hv_top5_hits"]) / 5.0)
                captures.append(float(match["hv_board_capture"]))
            rows.append(
                {
                    "name": name,
                    "n_boards": len(boards),
                    "mean_hv_top5_rate": _mean(hv_hits),
                    "mean_hv_board_capture": _mean(captures),
                }
            )
        out[regime] = {
            "n_boards": len(boards),
            "policies": rows,
        }
    return out


def render(payload: dict[str, object]) -> str:
    boards = payload["boards"]
    assert isinstance(boards, list)
    inventory = payload["inventory"]
    assert isinstance(inventory, dict)
    aggregate = payload["aggregate"]
    assert isinstance(aggregate, dict)
    lines = [
        "# HV/TDV board backtest, split by slate regime (#603)",
        "",
        f"Generated {payload['finished_at']}.",
        "",
        "Success metric is the Highest value board only: top-5 hits, and",
        "the share of that top 5's displayed Value the hits carry.",
        "Draft count and win frequency are not scored.",
        "",
        "Sunday multi-game and one-night (TNF, SNF, MNF) are separate samples.",
        "A rate measured on Sunday is not a MNF rate.",
        "",
        "Board pool: the visible Highest value section in the screenshots.",
        "That is not the full roster. Players off the board are absent.",
        "The optimizer counterfactual uses realized base as a perfect",
        "projection, then the live boost-rank blend, then picks five.",
        "It is not a walk-forward fit. Corpus C is empty, so the production",
        "model was not replayed.",
        "",
        "## Command",
        "",
        "```sh",
        str(payload["command"]),
        "```",
        "",
        "## Sunday boards",
        "",
    ]
    for board in boards:
        if not isinstance(board, dict):
            continue
        lines.append(
            f"### {board['slate_date']} `{board['regime']}` "
            f"law residual max {_num(board['law_max_abs_residual'], 2)}"
        )
        lines.append("")
        lines.append(f"HV/TDV top 5: {', '.join(board['hv_top5'])}")
        lines.append("")
        hv_pos = board["hv_top5_positions"]
        assert isinstance(hv_pos, dict)
        lines.append(
            f"HV/TDV top 5 positions: {hv_pos['kickers']} K, "
            f"{hv_pos['defenders']} DEF, {hv_pos['skill']} skill."
        )
        lines.append("")
        policy_rows = []
        policies = board["policies"]
        assert isinstance(policies, list)
        for item in policies:
            assert isinstance(item, dict)
            policy_rows.append(
                [
                    str(item["name"]),
                    str(item["hv_top5_hits"]),
                    _pct(float(item["hv_board_capture"])),
                    str(item["kickers"]),
                    str(item["defenders"]),
                ]
            )
        lines.append(
            _table(
                ["policy", "HV hits", "HV Value capture", "K", "DEF"],
                policy_rows,
            )
        )
        lines.append("")
    lines.extend(
        [
            "## Mean HV/TDV board rate by regime",
            "",
            "Hit rate is hits/5 on the board top 5. Value capture is the",
            "share of that top 5's displayed Value. `identity_uncapped` is",
            "the optimizer when the projected base is already the realized",
            "base. `boost_0.75` is the live blend on that correct base.",
            "One-night columns stay empty when no one-night board was scored.",
            "",
        ]
    )
    headers = [
        "policy",
        "sunday_multi hits",
        "sunday_multi Value",
        "one_night hits",
        "one_night Value",
    ]
    sunday = aggregate[SUNDAY_MULTI]
    assert isinstance(sunday, dict)
    sunday_policies = {str(row["name"]): row for row in sunday["policies"]}  # type: ignore[index]
    one_night_rows: list[dict[str, object]] = []
    for regime in ONE_NIGHT_REGIMES:
        block = aggregate[regime]
        assert isinstance(block, dict)
        policies = block["policies"]
        assert isinstance(policies, list)
        one_night_rows.extend(row for row in policies if isinstance(row, dict))
    table_rows = []
    for name, row in sunday_policies.items():
        assert isinstance(row, dict)
        table_rows.append(
            [
                name,
                f"{_pct(row['mean_hv_top5_rate'])} (n={row['n_boards']})",  # type: ignore[arg-type]
                f"{_pct(row['mean_hv_board_capture'])} (n={row['n_boards']})",  # type: ignore[arg-type]
                "n/a (n=0)",
                "n/a (n=0)",
            ]
        )
    if not table_rows:
        table_rows.append(["none", "n/a", "n/a", "n/a", "n/a"])
    lines.append(_table(headers, table_rows))
    lines.append("")
    for regime in ONE_NIGHT_REGIMES:
        block = aggregate[regime]
        assert isinstance(block, dict)
        lines.append(f"`{regime}` boards scored: {block['n_boards']}. HV/TDV rate: not run.")
        lines.append("")
    lines.extend(
        [
            "## Contest-day inventory (not an optimizer frequency)",
            "",
            "This is the early probe list in `drive/nfl_probe_out` "
            "(33 NFL contest days), not the later 91-contest Corpus C sweep. "
            "The sweep was not stored per day, so it cannot be split here.",
            "",
        ]
    )
    counts = inventory["counts"]
    assert isinstance(counts, dict)
    count_rows = [[str(key), str(counts[key])] for key in sorted(counts)]
    lines.append(_table(["regime", "finalized contest days"], count_rows))
    lines.append("")
    lines.append(
        "Same-day SNF sits inside `sunday_multi` when that Sunday also has "
        "two or more afternoon games. Those contest ids are not a separate "
        "SNF sample. TNF and MNF are their own days."
    )
    lines.append("")
    mnf = payload["mnf_t40"]
    assert isinstance(mnf, dict)
    lines.extend(
        [
            "## MNF T-40 game",
            "",
            f"{mnf['slate_date']} {mnf['matchup']} kickoff {mnf['gametime']} ET. "
            f"Regime `{mnf['regime']}`. Games that day: {mnf['game_count']}.",
            "",
            "## Recommended live knobs",
            "",
            str(payload["knobs_markdown"]),
            "",
        ]
    )
    return "\n".join(lines)


def _knobs_markdown(aggregate: dict[str, dict[str, object]]) -> str:
    sunday = aggregate[SUNDAY_MULTI]
    identity = next(row for row in sunday["policies"] if row["name"] == "identity_uncapped")  # type: ignore[union-attr]
    blend = next(row for row in sunday["policies"] if row["name"] == "boost_0.75_uncapped")  # type: ignore[union-attr]
    capped = next(row for row in sunday["policies"] if row["name"] == "boost_0.75_def1_k1")  # type: ignore[union-attr]
    return "\n".join(
        [
            "### sunday_multi",
            "",
            "- `NFL_OPTIMIZER_PROFILE=max_value`.",
            "- No defender cap and no kicker cap. Slot order stays joint.",
            "- On these two boards, perfect-base identity (the optimizer when "
            f"the base is already known, n={sunday['n_boards']}) hits the "
            f"HV/TDV top 5 at {_pct(identity['mean_hv_top5_rate'])} and captures "  # type: ignore[arg-type]
            f"{_pct(identity['mean_hv_board_capture'])} of that top 5's Value. "  # type: ignore[arg-type]
            "Sep 20's identity five includes two kickers. Sep 27's includes "
            "two defenders.",
            "- `boost_0.75` on that same perfect base hits the board at "
            f"{_pct(blend['mean_hv_top5_rate'])} and captures "  # type: ignore[arg-type]
            f"{_pct(blend['mean_hv_board_capture'])} of the board Value. "  # type: ignore[arg-type]
            "Max-1 defender and max-1 kicker on the blend captures "
            f"{_pct(capped['mean_hv_board_capture'])}.",  # type: ignore[arg-type]
            "- Leave the live ridge blend at `NFL_PICKER_BOOST_RANK_BLEND=0.75` "
            "until a regime-split refit replaces it. The 2026-09-25 sweep "
            "(identity 51.7%, boost 0.75 57.9%, 91 contests) is that ridge on "
            "a mixture of regimes. It is not this table and it is not MNF.",
            "",
            "### one_night_mnf (tonight), and TNF / SNF",
            "",
            "- Tonight is one game, PHI at CHI. Keep "
            "`NFL_OPTIMIZER_PROFILE=max_value` (floor 1/1). A two-game floor "
            "is the Sunday shape.",
            "- Keep `NFL_PICKER_BOOST_RANK_BLEND=0.75` as the live ridge "
            "setting. Do not flip it to identity because the Sunday "
            "perfect-base table prefers identity. That table is Sunday, and "
            "it assumes the base is already known. No one-night board was "
            "scored (n=0).",
            "- Do not add a defender cap or a kicker cap. Nothing one-night "
            "was measured, and the Sunday identity lineups use two kickers "
            "or two defenders. Do not copy that mix onto MNF as a quota.",
            "- Do not use the week-1 zero-boost both-quarterback archetype. "
            "Those four contests mix Thursday, Friday, Sunday, and Monday, "
            "and the boost table was all zeros. Tonight is week 3. Sunday's "
            "board already shows boosts up to +3.0x.",
            "- Slot-by-mean stays off.",
            "- The probe has zero standalone SNF contest days. SNF that "
            "shares a Sunday date is inside `sunday_multi`.",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hv-regime-backtest")
    parser.add_argument(
        "--boards",
        type=Path,
        nargs="+",
        default=[
            Path("tests/fixtures/hv_screenshot_boards/2026-09-20.json"),
            Path("tests/fixtures/hv_screenshot_boards/2026-09-27.json"),
        ],
    )
    parser.add_argument(
        "--schedule",
        type=Path,
        default=Path("data/schedule/schedules.csv"),
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        default=Path("../drive/nfl_probe_out/merged_summary.json"),
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--mnf-date", default="2026-09-28")
    args = parser.parse_args(argv)
    command = " ".join(sys.argv)
    board_payloads = []
    for path in args.boards:
        slate_date, regime, rows = _load_board(path)
        scored = score_board(rows, regime=regime)
        scored["slate_date"] = slate_date
        board_payloads.append(scored)
    games = load_schedules_csv(args.schedule)
    by_day: dict[date, list] = defaultdict(list)
    for game in games:
        if game.gameday is not None and game.kickoff_at is not None:
            by_day[game.gameday].append(game)
    counts: dict[str, int] = defaultdict(int)
    if args.inventory.is_file():
        for contest in _inventory(args.inventory):
            if contest.get("isFinalized") is False:
                continue
            day = date.fromisoformat(str(contest["day"]))
            kickoffs = tuple(game.kickoff_at for game in by_day.get(day, []) if game.kickoff_at)
            counts[regime_from_kickoffs(kickoffs)] += 1
    else:
        counts["inventory_missing"] = 1
    mnf_day = date.fromisoformat(args.mnf_date)
    mnf_games = by_day.get(mnf_day, [])
    if len(mnf_games) == 1 and mnf_games[0].kickoff_at is not None:
        game = mnf_games[0]
        matchup = f"{game.away_team} at {game.home_team}"
        assert game.kickoff_at is not None
        gametime = game.kickoff_at.astimezone(ZoneInfo("America/New_York")).strftime("%H:%M")
    else:
        matchup = "unresolved"
        gametime = "unresolved"
    aggregate = _aggregate(board_payloads)
    payload: dict[str, object] = {
        "kind": "hv_regime_backtest",
        "issue": 603,
        "command": command,
        "finished_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "boards": board_payloads,
        "aggregate": aggregate,
        "inventory": {"counts": dict(counts), "path": str(args.inventory)},
        "mnf_t40": {
            "slate_date": args.mnf_date,
            "matchup": matchup,
            "gametime": gametime,
            "game_count": len(mnf_games),
            "regime": regime_from_kickoffs(
                tuple(game.kickoff_at for game in mnf_games if game.kickoff_at)
            ),
        },
        "knobs_markdown": _knobs_markdown(aggregate),
        "contest_entry": False,
    }
    report = render(payload)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    args.report.write_text(report)
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
