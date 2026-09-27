"""Hard zero-boost gate until every NHL team has played this season.

Why (operator strategy, #501 / #453 / #325): the edge is the **gap** between
early slate games starting and every NHL team having >=1 GP. Through that
entire gap: ZERO BOOST. Field mispricing often assumes boosts are live;
never arm boost, ownership-fade, or leverage logic early. Fail closed: missing
or incomplete team-GP coverage keeps the boost multiplier at 0.0.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from nhl_oracle.contract.schema import BoostRegime

# NHL has 32 clubs in the current league shape; coverage must cover all of them.
NHL_EXPECTED_TEAM_COUNT = 32
BOOST_MULTIPLIER_GATED = 0.0
BOOST_MULTIPLIER_CLEARED = 1.0


@dataclass(frozen=True)
class TeamGamesPlayed:
    """One club's regular-season games played in the active season."""

    team_id: str
    games_played: int

    def __post_init__(self) -> None:
        if not str(self.team_id).strip():
            raise ValueError("team_id_required")
        if self.games_played < 0:
            raise ValueError("games_played_must_be_non_negative")


@dataclass(frozen=True)
class BoostEligibility:
    """Result of the hard all-teams-played gate."""

    boost_allowed: bool
    boost_multiplier: float
    teams_expected: int
    teams_observed: int
    teams_with_games: int
    teams_at_zero_gp: int
    zero_gp_team_ids: tuple[str, ...]
    detail: str

    @property
    def gate_cleared(self) -> bool:
        return self.boost_allowed


def _normalize_rows(
    team_games_played: Mapping[str, int] | Sequence[TeamGamesPlayed] | None,
) -> list[TeamGamesPlayed]:
    if team_games_played is None:
        return []
    if isinstance(team_games_played, Mapping):
        return [
            TeamGamesPlayed(team_id=str(team_id), games_played=int(games_played))
            for team_id, games_played in team_games_played.items()
        ]
    return list(team_games_played)


def evaluate_boost_eligibility(
    team_games_played: Mapping[str, int] | Sequence[TeamGamesPlayed] | None,
    *,
    expected_team_count: int = NHL_EXPECTED_TEAM_COUNT,
) -> BoostEligibility:
    """Return boost multiplier 0.0 until every expected team has >=1 GP.

    Fail closed: ``None``, empty, or fewer than ``expected_team_count`` teams
    keeps boost disabled. Any team still at 0 GP also keeps boost disabled.
    """

    if expected_team_count <= 0:
        raise ValueError("expected_team_count_must_be_positive")

    rows = _normalize_rows(team_games_played)
    by_team = {row.team_id: row.games_played for row in rows}
    observed = len(by_team)
    zero_ids = tuple(sorted(team_id for team_id, gp in by_team.items() if gp == 0))
    with_games = observed - len(zero_ids)

    if observed < expected_team_count:
        missing = expected_team_count - observed
        return BoostEligibility(
            boost_allowed=False,
            boost_multiplier=BOOST_MULTIPLIER_GATED,
            teams_expected=expected_team_count,
            teams_observed=observed,
            teams_with_games=with_games,
            teams_at_zero_gp=len(zero_ids) + missing,
            zero_gp_team_ids=zero_ids,
            detail=(
                "zero_boost_gate_incomplete_coverage "
                f"observed={observed}_of_{expected_team_count}; "
                "gap strategy: do not arm boost until all teams have played"
            ),
        )

    if zero_ids:
        return BoostEligibility(
            boost_allowed=False,
            boost_multiplier=BOOST_MULTIPLIER_GATED,
            teams_expected=expected_team_count,
            teams_observed=observed,
            teams_with_games=with_games,
            teams_at_zero_gp=len(zero_ids),
            zero_gp_team_ids=zero_ids,
            detail=(
                "zero_boost_gate_active "
                f"teams_at_zero_gp={len(zero_ids)}; "
                "early-slate gap: exploit field mispricing, never arm boost early"
            ),
        )

    return BoostEligibility(
        boost_allowed=True,
        boost_multiplier=BOOST_MULTIPLIER_CLEARED,
        teams_expected=expected_team_count,
        teams_observed=observed,
        teams_with_games=with_games,
        teams_at_zero_gp=0,
        zero_gp_team_ids=(),
        detail="zero_boost_gate_cleared all_teams_have_played",
    )


def force_none_while_gated(
    regime: BoostRegime,
    eligibility: BoostEligibility,
) -> tuple[BoostRegime, BoostEligibility]:
    """Force boosted regimes to ``NONE`` whenever the all-teams-played gate is closed.

    Even if live cards or historical draftStats look flat/positional, the hard
    gate wins through the early-slate gap. ``UNKNOWN`` stays unknown (honest
    card evidence) but ``effective_boost_multiplier`` remains 0.0 while gated.
    """

    if eligibility.boost_allowed:
        return regime, eligibility
    if regime in (BoostRegime.FLAT, BoostRegime.POSITIONAL):
        return BoostRegime.NONE, eligibility
    return regime, eligibility


def effective_boost_multiplier(
    team_games_played: Mapping[str, int] | Sequence[TeamGamesPlayed] | None,
    *,
    expected_team_count: int = NHL_EXPECTED_TEAM_COUNT,
    proposed_multiplier: float = BOOST_MULTIPLIER_CLEARED,
) -> float:
    """Clamp any proposed boost multiplier to 0.0 while the gate is closed."""

    eligibility = evaluate_boost_eligibility(
        team_games_played,
        expected_team_count=expected_team_count,
    )
    if not eligibility.boost_allowed:
        return BOOST_MULTIPLIER_GATED
    if proposed_multiplier < 0:
        raise ValueError("proposed_multiplier_must_be_non_negative")
    return float(proposed_multiplier)
