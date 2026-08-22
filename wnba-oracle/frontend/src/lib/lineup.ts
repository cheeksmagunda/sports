import type { FrozenLineupPayload, PlayerProjection } from "./api";

const LINEUP_SIZE = 5;

export type OrderedLineupRow = {
  player: PlayerProjection;
  slotMultiplier: number;
};

export type OrderedLineupResult =
  | { ok: true; rows: OrderedLineupRow[] }
  | { ok: false; error: string };

function contractError(error: string): OrderedLineupResult {
  return { ok: false, error };
}

function legacyPlaceholder(playerId: number): PlayerProjection {
  return {
    player_id: playerId,
    display_name: `Player ${playerId}`,
    team: "-",
    opponent: "-",
    position: "F",
    card_boost: 0,
    pred_real_score_p50: 0,
    pred_minutes_p10: 0,
    pred_minutes_p50: 0,
    pred_minutes_p90: 0,
  };
}

/**
 * Resolves a frozen lineup into its committed five-slot presentation order.
 * Projection array order is not authoritative; player_ids is.
 */
export function resolveOrderedLineup(
  lineup: FrozenLineupPayload,
): OrderedLineupResult {
  const playerIds = lineup.player_ids;
  if (
    !Array.isArray(playerIds) ||
    playerIds.length !== LINEUP_SIZE ||
    new Set(playerIds).size !== LINEUP_SIZE
  ) {
    return contractError("Expected exactly five unique player IDs.");
  }

  const slotMultipliers = lineup.slot_multipliers;
  if (
    !Array.isArray(slotMultipliers) ||
    slotMultipliers.length !== LINEUP_SIZE ||
    !slotMultipliers.every(
      (multiplier) => Number.isFinite(multiplier) && multiplier > 0,
    )
  ) {
    return contractError(
      "Expected exactly five finite, positive slot multipliers.",
    );
  }

  const projections = lineup.per_player;
  if (
    projections === undefined ||
    (Array.isArray(projections) && projections.length === 0)
  ) {
    return {
      ok: true,
      rows: playerIds.map((playerId, index) => ({
        player: legacyPlaceholder(playerId),
        slotMultiplier: slotMultipliers[index],
      })),
    };
  }

  if (!Array.isArray(projections)) {
    return contractError("Expected per-player projections to be an array.");
  }

  const projectionIds = projections.map(
    (projection) => projection?.player_id,
  );
  const playerIdSet = new Set(playerIds);
  if (
    projections.length !== LINEUP_SIZE ||
    new Set(projectionIds).size !== LINEUP_SIZE ||
    !projectionIds.every((playerId) => playerIdSet.has(playerId))
  ) {
    return contractError(
      "Per-player projections must contain the exact five unique lineup player IDs.",
    );
  }

  const projectionById = new Map(
    projections.map((projection) => [projection.player_id, projection]),
  );
  const rows: OrderedLineupRow[] = [];
  for (const [index, playerId] of playerIds.entries()) {
    const player = projectionById.get(playerId);
    if (!player) {
      return contractError(
        "Per-player projections must contain the exact five unique lineup player IDs.",
      );
    }
    rows.push({ player, slotMultiplier: slotMultipliers[index] });
  }

  return { ok: true, rows };
}
