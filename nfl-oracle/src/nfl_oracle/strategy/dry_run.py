"""Offline contest dry-run: five-card shadow slate from fixtures.

Observation / dry_run only. Always hard-denies real submit via
``FiveCardProviderStub.submit``. Never authenticates to Real Sports or mutates
provider state.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal

from nfl_oracle.baselines.player_priors import fit_player_means, predict_player_prior
from nfl_oracle.labels.extract import load_labels_from_corpus_root
from nfl_oracle.labels.schema import ValueLabel
from nfl_oracle.strategy.algebra import (
    OBSERVED_DEFAULT_SLOT_MULTIPLIERS,
    contest_score_to_json,
    contest_shadow_score,
)
from nfl_oracle.strategy.enumerate import best_shadow_ordering, rank_shadow_orderings
from nfl_oracle.strategy.gates import evaluate_entry_gates
from nfl_oracle.strategy.schema import FiveCardAction
from nfl_oracle.strategy.value_preds import resolve_shadow_values, value_model_strategy_note

ValueSource = Literal["player_position_prior", "feature_ridge"]


@dataclass(frozen=True)
class SlateCandidateGame:
    season: int
    game_id: int
    players: tuple[ValueLabel, ...]


def default_value_label_fixture_root() -> Path:
    """Bundled offline value-label fixtures (CI-safe; no Real Sports auth)."""

    return Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "value_labels"


def pick_decision_slate(
    labels: Sequence[ValueLabel],
    *,
    decision_season: int | None = None,
    min_players: int = 5,
) -> SlateCandidateGame:
    """Pick a decision-season game with at least ``min_players`` labeled players.

    Prefers the latest season, then the game with the most labeled players
    (stable tie-break on game_id).
    """

    if not labels:
        raise ValueError("no_labels_for_offline_dry_run")

    seasons = sorted({row.season for row in labels})
    season = decision_season if decision_season is not None else seasons[-1]
    season_rows = [row for row in labels if row.season == season]
    if not season_rows:
        raise ValueError(f"no_labels_for_decision_season:{season}")

    by_game: dict[int, list[ValueLabel]] = defaultdict(list)
    for row in season_rows:
        by_game[row.game_id].append(row)

    candidates: list[SlateCandidateGame] = []
    for game_id, rows in by_game.items():
        # Distinct players only (keep first row per player_id).
        seen: dict[int, ValueLabel] = {}
        for row in rows:
            seen.setdefault(row.player_id, row)
        distinct = tuple(seen.values())
        if len(distinct) >= min_players:
            candidates.append(SlateCandidateGame(season=season, game_id=game_id, players=distinct))

    if not candidates:
        raise ValueError(f"no_game_with_{min_players}_players_in_season_{season}")

    candidates.sort(key=lambda c: (-len(c.players), c.game_id))
    return candidates[0]


def _prior_values_for_slate(
    train: Sequence[ValueLabel],
    slate_players: Sequence[ValueLabel],
) -> dict[int, float]:
    player_mean, pos_mean, global_mean = fit_player_means(list(train))
    player_n: dict[int, int] = defaultdict(int)
    for row in train:
        player_n[row.player_id] += 1
    values: dict[int, float] = {}
    for row in slate_players:
        prior = predict_player_prior(
            player_id=row.player_id,
            position=row.position,
            player_mean=player_mean,
            pos_mean=pos_mean,
            global_mean=global_mean,
            player_n=dict(player_n),
        )
        values[row.player_id] = float(prior.mean_value)
    return values


def select_five_card_set(
    slate_players: Sequence[ValueLabel],
    values_by_player: dict[int, float],
) -> tuple[int, int, int, int, int]:
    """Take the top-5 distinct players by shadow value (stable id tie-break)."""

    ranked = sorted(
        slate_players,
        key=lambda row: (-float(values_by_player.get(row.player_id, 0.0)), row.player_id),
    )
    if len(ranked) < 5:
        raise ValueError(f"slate_needs_five_players_got_{len(ranked)}")
    ids = tuple(int(row.player_id) for row in ranked[:5])
    return (ids[0], ids[1], ids[2], ids[3], ids[4])


def prove_submit_hard_denied(action: FiveCardAction) -> dict[str, Any]:
    """Attempt stub.submit and record the hard deny (never succeeds)."""

    from nfl_oracle.providers.five_card import FiveCardProviderStub, ProviderNotReady

    stub = FiveCardProviderStub()
    try:
        stub.submit(action)
    except ProviderNotReady as exc:
        return {
            "submit_attempted": True,
            "submit_denied": True,
            "submit_error": str(exc),
            "contest_entry": False,
        }
    # Unreachable by policy; defensive if stub is ever weakened.
    return {
        "submit_attempted": True,
        "submit_denied": False,
        "submit_error": "unexpected_submit_success",
        "contest_entry": False,
        "policy_violation": True,
    }


def build_offline_contest_dry_run(
    *,
    corpus_root: Path | str | None = None,
    labels: Sequence[ValueLabel] | None = None,
    decision_season: int | None = None,
    use_feature_ridge: bool = False,
    alpha: float = 1.0,
    top_k_orderings: int = 5,
    prove_submit_denied: bool = True,
    include_schedule_slate: bool = False,
    schedule_week: int | None = None,
    schedule_date: date | None = None,
    project_root: Path | str | None = None,
) -> dict[str, Any]:
    """Produce a five-card shadow slate from offline fixtures (dry_run).

    Default value path uses walk-forward player/position priors (no ridge fit).
    Opt into ``use_feature_ridge`` for leakage-safe prior-feature ridge values.
    Optionally attach an offline schedule week slate (games/opponents) when
    ``include_schedule_slate`` is set — observation only; never enables entry.
    """

    if labels is None:
        root = Path(corpus_root) if corpus_root is not None else default_value_label_fixture_root()
        labels = load_labels_from_corpus_root(root)
        root_str = str(root)
    else:
        root_str = str(corpus_root) if corpus_root is not None else "(in-memory labels)"

    if not labels:
        raise ValueError("no_labels_for_offline_dry_run")

    slate = pick_decision_slate(labels, decision_season=decision_season)
    train = [row for row in labels if row.season < slate.season]
    positions = {row.player_id: row.position for row in slate.players}

    if use_feature_ridge:
        if not train:
            raise ValueError("train_labels_required_for_feature_ridge_dry_run")
        if len(slate.players) < 5:
            raise ValueError(f"slate_needs_five_players_got_{len(slate.players)}")
        # Predict for full slate pool, then select top-5 by ridge value.
        all_ids = [row.player_id for row in slate.players]
        values, value_meta = resolve_shadow_values(
            player_ids=all_ids,
            values_by_player={},
            use_feature_value_model=True,
            player_positions=positions,
            decision_season=slate.season,
            train_labels=train,
            alpha=alpha,
        )
        value_source: ValueSource = "feature_ridge"
    else:
        values = _prior_values_for_slate(train, slate.players)
        value_meta = {
            **value_model_strategy_note(),
            "value_source": "player_position_prior",
            "use_feature_value_model": False,
            "default_offline_safe": True,
            "n_train_labels": len(train),
            "decision_season": slate.season,
        }
        value_source = "player_position_prior"

    player_ids = select_five_card_set(slate.players, values)
    # Restrict values map to the five-card set for scoring clarity.
    five_values = {pid: float(values.get(pid, 0.0)) for pid in player_ids}

    best, best_total = best_shadow_ordering(
        player_ids,
        five_values,
        slot_multipliers=OBSERVED_DEFAULT_SLOT_MULTIPLIERS,
        use_contest_algebra=True,
    )
    ranked = rank_shadow_orderings(
        player_ids,
        five_values,
        slot_multipliers=OBSERVED_DEFAULT_SLOT_MULTIPLIERS,
        top_k=top_k_orderings,
        use_contest_algebra=True,
    )
    score = contest_shadow_score(
        best,
        five_values,
    )
    action = FiveCardAction(
        player_ids=best.player_ids,
        slot_multipliers=OBSERVED_DEFAULT_SLOT_MULTIPLIERS,
        notes="offline_contest_dry_run",
    )
    from nfl_oracle.providers.five_card import FiveCardProviderStub

    preview = FiveCardProviderStub().shadow_preview(action)
    gates = evaluate_entry_gates()
    submit_proof = (
        prove_submit_hard_denied(action)
        if prove_submit_denied
        else {
            "submit_attempted": False,
            "submit_denied": True,
            "contest_entry": False,
            "note": "submit_proof_skipped",
        }
    )

    pool = [
        {
            "player_id": row.player_id,
            "position": row.position,
            "team_id": row.team_id,
            "shadow_value": float(values.get(row.player_id, 0.0)),
            "fixture_label_value": float(row.value),
            "selected": row.player_id in player_ids,
        }
        for row in sorted(
            slate.players,
            key=lambda r: (-float(values.get(r.player_id, 0.0)), r.player_id),
        )
    ]

    schedule_slate_payload: dict[str, Any] | None = None
    if include_schedule_slate:
        from nfl_oracle.calendar.slate import research_schedule_slate

        root_for_sched = Path(project_root) if project_root is not None else None
        week = schedule_week if schedule_week is not None else 1
        season_for_sched = slate.season
        if schedule_date is not None:
            schedule_slate_payload = research_schedule_slate(
                project_root=root_for_sched,
                day=schedule_date,
            )
        else:
            schedule_slate_payload = research_schedule_slate(
                project_root=root_for_sched,
                season=season_for_sched,
                week=week,
            )

    return {
        "name": "nfl_offline_contest_dry_run",
        "version": 1,
        "mode": "dry_run",
        "dry_run": True,
        "observation_only": True,
        "contest_entry": False,
        "submit_enabled": False,
        "provider_contract_verified": False,
        "corpus_root": root_str,
        "decision_season": slate.season,
        "decision_game_id": slate.game_id,
        "value_source": value_source,
        "use_feature_ridge": use_feature_ridge,
        "value_model": value_meta,
        "values_by_player": {str(k): v for k, v in five_values.items()},
        "player_positions": {str(k): positions[k] for k in player_ids if k in positions},
        "five_card_set": list(player_ids),
        "best_ordering": {
            "player_ids": list(best.player_ids),
            "slot_multipliers": list(OBSERVED_DEFAULT_SLOT_MULTIPLIERS),
            "total": best_total,
            "contest_entry": False,
            "dry_run": True,
            "observation_only": True,
        },
        "contest_shadow_score": contest_score_to_json(score),
        "rankings": ranked,
        "slate_pool": pool,
        "shadow_preview": preview,
        "entry_gates": gates.to_json_obj(),
        "submit_proof": submit_proof,
        "n_labels_total": len(labels),
        "n_train_labels": len(train),
        "schedule_slate": schedule_slate_payload,
        "policy": "offline_dry_run_hard_denies_real_submit",
        "issue_refs": ["#89", "#91"],
    }
