"""Player-level recent-value prior scaffold (walk-forward safe).

Fits only on seasons strictly earlier than the evaluation season. Identity
continuity across Corpus G anchors is still an open audit — treat outputs as
baselines, not contest edge claims.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from nfl_oracle.labels.schema import ValueLabel


@dataclass(frozen=True)
class PlayerPrior:
    player_id: int
    mean_value: float
    n_games: int
    fallback: str  # "player" | "position" | "global"


def fit_player_means(train: list[ValueLabel]) -> tuple[dict[int, float], dict[str, float], float]:
    """Return player means, position means, and global mean from train labels."""

    by_player: dict[int, list[float]] = defaultdict(list)
    by_pos: dict[str, list[float]] = defaultdict(list)
    all_vals: list[float] = []
    for row in train:
        by_player[row.player_id].append(row.value)
        by_pos[row.position].append(row.value)
        all_vals.append(row.value)
    player_mean = {pid: sum(vs) / len(vs) for pid, vs in by_player.items() if vs}
    pos_mean = {pos: sum(vs) / len(vs) for pos, vs in by_pos.items() if vs}
    global_mean = sum(all_vals) / len(all_vals) if all_vals else 0.0
    return player_mean, pos_mean, global_mean


def predict_player_prior(
    *,
    player_id: int,
    position: str,
    player_mean: dict[int, float],
    pos_mean: dict[str, float],
    global_mean: float,
    min_games: int = 1,
    player_n: dict[int, int] | None = None,
) -> PlayerPrior:
    """Prefer player mean when enough history; else position; else global."""

    n = (player_n or {}).get(player_id, 1 if player_id in player_mean else 0)
    if player_id in player_mean and n >= min_games:
        return PlayerPrior(player_id, player_mean[player_id], n, "player")
    if position in pos_mean:
        return PlayerPrior(player_id, pos_mean[position], n, "position")
    return PlayerPrior(player_id, global_mean, n, "global")
