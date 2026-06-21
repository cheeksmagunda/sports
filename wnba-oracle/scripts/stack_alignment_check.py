"""Game-stack alignment audit (post-mortem item 2).

For each model-era slate (>= 2026-06-01) the post-mortem flagged that game
stacks appear in ~80% of winning lineups. This script measures how often OUR
served lineup aligns with the WINNING lineup's game stack -- i.e. how often our
top-5 holds 2+ players from a team the contest winner stacked.

Data bridge: contest_leaderboards stores each player's integer `teamId`, while
frozen_lineups.per_player stores the team abbreviation (`team`). We learn the
teamId -> team_key map by joining contest_leaderboards.playerId to
slate_labels.platform_player_id (majority vote across all slates), then express
the winner's stack in the same team-abbreviation space as our picks.

Definitions (per slate):
  - winner stack teams = {team_key : the rank-1 lineup plays >= 2 of that team}.
  - our pick team counts = per-team count of our served (max freeze_seq) lineup.
  - ALIGNED (primary) = our picks include >= 2 players whose team is in the
    winner's stack-team set (2+ players from the winning game stack).
  - aligned_same_team (strict) = we hold >= 2 on a SINGLE winner-stacked team.

Usage:
  uv run python scripts/stack_alignment_check.py
  (reads DATABASE_PUBLIC_URL from the environment; read-only)
"""

from __future__ import annotations

import os
from collections import Counter, defaultdict

import psycopg

MODEL_ERA_START = "2026-06-01"


def _connect() -> psycopg.Connection:
    url = os.environ.get("DATABASE_PUBLIC_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_PUBLIC_URL / DATABASE_URL not set in environment")
    return psycopg.connect(url, connect_timeout=20)


def build_teamid_to_key(cur: psycopg.Cursor) -> dict[int, str]:
    """teamId -> team_key via playerId == platform_player_id majority vote."""
    cur.execute("select lineup from contest_leaderboards")
    pid_team: dict[int, int] = {}
    for (lu,) in cur.fetchall():
        if not isinstance(lu, list):
            continue
        for p in lu:
            tid = p.get("teamId")
            pid = p.get("playerId")
            if tid is not None and pid is not None:
                pid_team[int(pid)] = int(tid)
    cur.execute(
        "select distinct platform_player_id, team_key from slate_labels "
        "where team_key is not null and team_key <> 'UNK'"
    )
    pid_key = {int(a): b for a, b in cur.fetchall() if a is not None}
    votes: dict[int, Counter[str]] = defaultdict(Counter)
    for pid, tid in pid_team.items():
        k = pid_key.get(pid)
        if k:
            votes[tid][k] += 1
    return {tid: c.most_common(1)[0][0] for tid, c in votes.items() if c}


def winner_team_counts(lineup: list[dict], teamid_to_key: dict[int, str]) -> Counter[str]:
    c: Counter[str] = Counter()
    for p in lineup:
        tid = p.get("teamId")
        if tid is None:
            continue
        key = teamid_to_key.get(int(tid), f"team{int(tid)}")
        c[key] += 1
    return c


def our_team_counts(lineup: dict) -> Counter[str]:
    c: Counter[str] = Counter()
    for p in lineup.get("per_player", []) or []:
        t = p.get("team")
        if t:
            c[t] += 1
    return c


def main() -> int:
    with _connect() as conn, conn.cursor() as cur:
        teamid_to_key = build_teamid_to_key(cur)

        # Served lineup per model-era slate = the row with the highest
        # freeze_seq (the last freeze that actually served).
        cur.execute(
            """
            select distinct on (slate_date) slate_date, freeze_seq, lineup
            from frozen_lineups
            where slate_date >= %s
            order by slate_date, freeze_seq desc
            """,
            (MODEL_ERA_START,),
        )
        frozen = {str(sd): lu for sd, _seq, lu in cur.fetchall()}

        # Winning contest lineup per slate (rank 1).
        cur.execute(
            """
            select distinct on (slate_date) slate_date, score, lineup
            from contest_leaderboards
            where slate_date >= %s
            order by slate_date, rank asc
            """,
            (MODEL_ERA_START,),
        )
        winners = {str(sd): (score, lu) for sd, score, lu in cur.fetchall()}

    slates = sorted(set(frozen) & set(winners))

    print(f"Game-stack alignment audit -- {len(slates)} model-era slates "
          f"(>= {MODEL_ERA_START})\n")
    header = (
        f"{'slate':<12} {'winner stack(2+)':<22} {'our teams':<22} "
        f"{'inStack':>7} {'align':>6} {'same':>5}"
    )
    print(header)
    print("-" * len(header))

    n_aligned = 0
    n_same_team = 0
    n_we_stacked = 0
    n_total = 0
    rows_out = []
    for sd in slates:
        our_lu = frozen[sd]
        _score, win_lu = winners[sd]
        if not isinstance(win_lu, list):
            continue
        our_cnt = our_team_counts(our_lu)
        if sum(our_cnt.values()) == 0:
            # Empty / no-player frozen lineup (e.g. a forfeit row); skip.
            continue
        win_cnt = winner_team_counts(win_lu, teamid_to_key)
        stack_teams = {t for t, n in win_cnt.items() if n >= 2}

        in_stack = sum(n for t, n in our_cnt.items() if t in stack_teams)
        aligned = in_stack >= 2
        same_team = any(our_cnt.get(t, 0) >= 2 for t in stack_teams)
        we_stacked = any(n >= 2 for n in our_cnt.values())

        n_total += 1
        n_aligned += int(aligned)
        n_same_team += int(same_team)
        n_we_stacked += int(we_stacked)

        stack_str = ", ".join(f"{t}:{win_cnt[t]}" for t in sorted(stack_teams)) or "(none)"
        our_str = ", ".join(f"{t}:{n}" for t, n in sorted(our_cnt.items()))
        print(
            f"{sd:<12} {stack_str:<22} {our_str:<22} "
            f"{in_stack:>7} {'YES' if aligned else 'no':>6} "
            f"{'YES' if same_team else '-':>5}"
        )
        rows_out.append((sd, aligned, same_team, we_stacked))

    print("-" * len(header))
    if n_total:
        print(
            f"\nSlates audited:                 {n_total}"
            f"\nOur lineups that held any 2+ stack: {n_we_stacked} "
            f"({100*n_we_stacked/n_total:.0f}%)"
            f"\nALIGNED (2+ from winner stack): {n_aligned}/{n_total} "
            f"= {100*n_aligned/n_total:.1f}%"
            f"\n  strict (2+ on one winner-stacked team): {n_same_team}/{n_total} "
            f"= {100*n_same_team/n_total:.1f}%"
        )
        print(
            f"\nThreshold: 60%. Primary alignment is "
            f"{'BELOW' if 100*n_aligned/n_total < 60 else 'AT/ABOVE'} threshold."
        )
    else:
        print("\nNo slates with both a frozen lineup and a winning leaderboard.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
