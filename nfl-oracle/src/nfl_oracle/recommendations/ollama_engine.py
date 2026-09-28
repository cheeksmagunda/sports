"""Ollama JSON utilities over optimizer candidate lineups.

Ridge, picker knobs, and the optimizer search stay in place. This module
runs a simulation matrix of at least 1000 draws and asks the Ollama HTTP
client for utilities. It never adds a player. Transport errors, timeouts,
and a response that does not repeat the candidate ids fall back to classic
contest utility. ``NFL_OLLAMA_ENGINE=0`` skips the call.
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Protocol, cast

from nfl_oracle.common.logging import get_logger
from nfl_oracle.recommendations.model import Projection

log = get_logger("nfl_oracle.recommendations.ollama_engine")

MIN_SIMULATIONS = 1000
MAX_LINEUPS = 12
DEFAULT_TIMEOUT_S = 8.0
_ON = frozenset({"1", "true", "yes", "on"})
_OFF = frozenset({"0", "false", "no", "off"})

_client_module: Any | None = None
_client_loaded = False


class OllamaJsonClient(Protocol):
    def __call__(self, prompt: str, *, timeout_s: float) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class EngineSelection:
    player_ids: tuple[int, ...]
    expected: float
    simulated_p90: float
    simulated_field_win_rate: float
    simulations: int
    ollama_utility: float


def ollama_engine_from_env(env: Mapping[str, str]) -> bool:
    """Return whether serving should score candidates with the Ollama engine.

    Unset enables the engine. ``0`` / ``false`` / ``off`` / ``no`` restore
    classic contest utility. Any other value fails closed.
    """

    raw = (env.get("NFL_OLLAMA_ENGINE") or "").strip().lower()
    if raw == "" or raw in _ON:
        return True
    if raw in _OFF:
        return False
    raise ValueError("NFL_OLLAMA_ENGINE_invalid")


def candidate_client_paths() -> tuple[Path, ...]:
    """Locations of the shared Ollama HTTP client (no NFL pick rules)."""

    here = Path(__file__).resolve()
    repo_root = here.parents[4]
    return (
        repo_root / "scripts" / "ollama_hv_watcher" / "client.py",
        Path("/app/scripts/ollama_hv_watcher/client.py"),
    )


def load_client_module() -> Any | None:
    """Load ``ollama_hv_watcher/client.py`` by path so app code does not own it."""

    global _client_loaded, _client_module
    if _client_loaded:
        return _client_module
    _client_loaded = True
    path = next((item for item in candidate_client_paths() if item.is_file()), None)
    if path is None:
        _client_module = None
        return None
    spec = importlib.util.spec_from_file_location("ollama_hv_watcher_client", path)
    if spec is None or spec.loader is None:
        _client_module = None
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _client_module = module
    return module


def score_candidates(
    lineups: Sequence[tuple[float, tuple[int, ...]]],
    projections: Sequence[Projection],
    *,
    boost_by_player: Mapping[int, float],
    game_by_player: Mapping[int, int],
    scorer: Callable[[float, float, float], float],
    slots: Sequence[float],
    game_ids: Sequence[int],
    ownership: Mapping[int, float],
    seed: int,
    game_correlation: float,
    simulations: int,
    field_slot_by_p90: bool,
    client: OllamaJsonClient | None = None,
    environ: Mapping[str, str] | None = None,
) -> EngineSelection | None:
    """Score candidate lineups. ``None`` means the caller keeps classic utility."""

    capped = _cap_lineups(lineups)
    if not capped:
        log.warning("ollama_engine_fallback", reason="no_candidates")
        return None
    env = environ if environ is not None else os.environ
    try:
        timeout_s = _timeout_s(env)
        n_sims = max(MIN_SIMULATIONS, int(simulations))
        summaries = _simulate(
            capped,
            projections,
            boost_by_player=boost_by_player,
            game_by_player=game_by_player,
            scorer=scorer,
            slots=slots,
            game_ids=game_ids,
            ownership=ownership,
            seed=seed,
            game_correlation=game_correlation,
            simulations=n_sims,
            field_slot_by_p90=field_slot_by_p90,
        )
        prompt = build_utility_prompt(
            capped,
            summaries,
            projections=projections,
            boost_by_player=boost_by_player,
            game_by_player=game_by_player,
            ownership=ownership,
            slots=slots,
            simulations=n_sims,
        )
        payload = _invoke(prompt, timeout_s=timeout_s, client=client, env=env)
        utilities = utilities_from_payload(payload, capped)
    except (
        OSError,
        TimeoutError,
        RuntimeError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
    ) as exc:
        log.warning("ollama_engine_fallback", reason=type(exc).__name__)
        return None
    if utilities is None:
        log.warning("ollama_engine_fallback", reason="invalid_utility_json")
        return None
    chosen = max(
        range(len(capped)),
        key=lambda index: (
            utilities[index],
            capped[index][0],
            tuple(-player_id for player_id in capped[index][1]),
        ),
    )
    expected, player_ids = capped[chosen]
    summary = summaries[chosen]
    log.info(
        "ollama_engine_selected",
        simulations=n_sims,
        lineup_count=len(capped),
        utility=utilities[chosen],
    )
    return EngineSelection(
        player_ids=player_ids,
        expected=expected,
        simulated_p90=summary["sim_p90"],
        simulated_field_win_rate=summary["field_win_rate"],
        simulations=n_sims,
        ollama_utility=utilities[chosen],
    )


def build_utility_prompt(
    lineups: Sequence[tuple[float, tuple[int, ...]]],
    summaries: Sequence[Mapping[str, float]],
    *,
    projections: Sequence[Projection],
    boost_by_player: Mapping[int, float],
    game_by_player: Mapping[int, int],
    ownership: Mapping[int, float],
    slots: Sequence[float],
    simulations: int,
) -> str:
    """JSON request. The model may only echo player ids already listed."""

    used: set[int] = {player_id for _, ids in lineups for player_id in ids}
    by_id = {projection.player_id: projection for projection in projections}
    players = [
        {
            "player_id": player_id,
            "mean": by_id[player_id].mean,
            "boost": boost_by_player[player_id],
            "game_id": game_by_player[player_id],
            "ownership": ownership[player_id],
        }
        for player_id in sorted(used)
    ]
    rows = [
        {
            "lineup_id": index,
            "players": list(player_ids),
            "expected": expected,
            "sim_mean": summaries[index]["sim_mean"],
            "sim_p90": summaries[index]["sim_p90"],
            "field_win_rate": summaries[index]["field_win_rate"],
        }
        for index, (expected, player_ids) in enumerate(lineups)
    ]
    return json.dumps(
        {
            "task": "score_candidate_lineups",
            "simulations": simulations,
            "slot_multipliers": list(slots),
            "rules": [
                "Return a JSON object with key utilities.",
                "Include every lineup_id exactly once.",
                "players must equal the given player ids in the same order.",
                "Do not add, drop, or invent player ids.",
                "utility is a finite number. Higher is better.",
            ],
            "players": players,
            "lineups": rows,
        },
        sort_keys=True,
    )


def _not_player_id(player_id: object) -> bool:
    return isinstance(player_id, bool) or not isinstance(player_id, int)


def utilities_from_payload(
    payload: Mapping[str, Any],
    lineups: Sequence[tuple[float, tuple[int, ...]]],
) -> dict[int, float] | None:
    """Accept utilities only when every lineup's player ids match exactly."""

    rows = payload.get("utilities") if isinstance(payload, Mapping) else None
    if not isinstance(rows, list) or len(rows) != len(lineups):
        return None
    found: dict[int, float] = {}
    for row in rows:
        if not isinstance(row, dict):
            return None
        lineup_id = row.get("lineup_id")
        players = row.get("players")
        utility = row.get("utility")
        if isinstance(lineup_id, bool) or not isinstance(lineup_id, int):
            return None
        if lineup_id < 0 or lineup_id >= len(lineups) or lineup_id in found:
            return None
        if not isinstance(players, list) or len(players) != len(lineups[lineup_id][1]):
            return None
        if any(_not_player_id(player_id) for player_id in players):
            return None
        player_ids = tuple(players)
        if player_ids != lineups[lineup_id][1]:
            return None
        if isinstance(utility, bool) or not isinstance(utility, (int, float)):
            return None
        if not math.isfinite(float(utility)):
            return None
        found[lineup_id] = float(utility)
    if set(found) != set(range(len(lineups))):
        return None
    return found


def _cap_lineups(
    lineups: Sequence[tuple[float, tuple[int, ...]]],
) -> list[tuple[float, tuple[int, ...]]]:
    ordered = sorted(lineups, key=lambda item: (-item[0], item[1]))
    capped: list[tuple[float, tuple[int, ...]]] = []
    seen: set[tuple[int, ...]] = set()
    for expected, player_ids in ordered:
        if len(player_ids) != 5 or player_ids in seen:
            continue
        seen.add(player_ids)
        capped.append((expected, player_ids))
        if len(capped) >= MAX_LINEUPS:
            break
    return capped


def _timeout_s(env: Mapping[str, str]) -> float:
    raw = (env.get("NFL_OLLAMA_TIMEOUT_S") or "").strip()
    if not raw:
        return DEFAULT_TIMEOUT_S
    value = float(raw)
    if not math.isfinite(value) or not 0 < value <= 120:
        raise ValueError("NFL_OLLAMA_TIMEOUT_S_out_of_range")
    return value


def _invoke(
    prompt: str,
    *,
    timeout_s: float,
    client: OllamaJsonClient | None,
    env: Mapping[str, str],
) -> Mapping[str, Any]:
    if client is not None:
        return dict(client(prompt, timeout_s=timeout_s))
    module = load_client_module()
    if module is None:
        raise FileNotFoundError("ollama_client_missing")
    host = (env.get("NFL_OLLAMA_HOST") or module.DEFAULT_HOST).strip() or module.DEFAULT_HOST
    model = (env.get("NFL_OLLAMA_MODEL") or module.DEFAULT_MODEL).strip() or module.DEFAULT_MODEL
    health = module.health_check(host, timeout_s=min(0.5, timeout_s))
    if not isinstance(health, dict) or not health.get("ok"):
        detail = health.get("error") if isinstance(health, dict) else "ollama_unhealthy"
        raise ConnectionError(str(detail or "ollama_unhealthy"))
    return cast(
        Mapping[str, Any],
        module.generate_json(prompt, host=host, model=model, timeout_s=timeout_s),
    )


def _simulate(
    lineups: Sequence[tuple[float, tuple[int, ...]]],
    projections: Sequence[Projection],
    *,
    boost_by_player: Mapping[int, float],
    game_by_player: Mapping[int, int],
    scorer: Callable[[float, float, float], float],
    slots: Sequence[float],
    game_ids: Sequence[int],
    ownership: Mapping[int, float],
    seed: int,
    game_correlation: float,
    simulations: int,
    field_slot_by_p90: bool,
) -> list[dict[str, float]]:
    """Correlated sample draws. Same shock law as the classic optimizer sims."""

    if simulations < MIN_SIMULATIONS:
        raise ValueError("ollama_engine_simulations_below_minimum")
    sorted_samples = {
        projection.player_id: tuple(sorted(projection.samples)) for projection in projections
    }
    p90_key = {
        projection.player_id: _sample_p90(sorted_samples[projection.player_id], projection.mean)
        for projection in projections
    }
    rng = random.Random(seed)
    shared = math.sqrt(game_correlation)
    idiosyncratic = math.sqrt(1 - game_correlation)
    lineup_totals: list[list[float]] = [[] for _ in lineups]
    field_scores: list[float] = []
    for _ in range(simulations):
        shocks = {game_id: rng.gauss(0, 1) for game_id in game_ids}
        values: dict[int, float] = {}
        for projection in projections:
            player_id = projection.player_id
            z = shared * shocks[game_by_player[player_id]]
            z += idiosyncratic * rng.gauss(0, 1)
            percentile = 0.5 * (1 + math.erf(z / math.sqrt(2)))
            samples = sorted_samples[player_id]
            draw = samples[min(len(samples) - 1, int(percentile * len(samples)))]
            values[player_id] = draw if rng.random() < projection.availability_probability else 0.0
        for index, (_, player_ids) in enumerate(lineups):
            lineup_totals[index].append(
                sum(
                    scorer(values[player_id], slots[slot], boost_by_player[player_id])
                    for slot, player_id in enumerate(player_ids)
                )
            )
        field_selected = sorted(
            projections,
            key=lambda projection: (
                math.log(max(rng.random(), 1e-12)) / max(0.001, ownership[projection.player_id])
            ),
            reverse=True,
        )[:5]
        if field_slot_by_p90:
            field_selected.sort(key=lambda projection: -p90_key[projection.player_id])
        else:
            field_selected.sort(key=lambda projection: -projection.mean)
        field_scores.append(
            sum(
                scorer(
                    values[projection.player_id],
                    slots[slot],
                    boost_by_player[projection.player_id],
                )
                for slot, projection in enumerate(field_selected)
            )
        )
    summaries: list[dict[str, float]] = []
    for totals in lineup_totals:
        ordered = sorted(totals)
        p90 = ordered[int(0.9 * (len(ordered) - 1))]
        wins = mean(
            float(left > right) + 0.5 * float(left == right)
            for left, right in zip(totals, field_scores, strict=True)
        )
        summaries.append({"sim_mean": mean(totals), "sim_p90": p90, "field_win_rate": wins})
    return summaries


def _sample_p90(samples: Sequence[float], fallback: float) -> float:
    if not samples:
        return fallback
    return samples[min(len(samples) - 1, int(0.9 * (len(samples) - 1)))]
