import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { Slip } from "../components/Slip";
import type {
  FrozenLineup,
  FrozenLineupPayload,
  PlayerProjection,
} from "./api";
import { resolveOrderedLineup } from "./lineup";

function projection(playerId: number): PlayerProjection {
  return {
    player_id: playerId,
    display_name: `Player ${playerId}`,
    team: "NYL",
    opponent: "IND",
    position: "G",
    card_boost: 0,
    pred_real_score_p50: playerId * 10,
    pred_minutes_p10: 20,
    pred_minutes_p50: 25,
    pred_minutes_p90: 30,
  };
}

function payload(
  overrides: Partial<FrozenLineupPayload> = {},
): FrozenLineupPayload {
  return {
    player_ids: [11, 22, 33, 44, 55],
    slot_multipliers: [1.5, 1.3, 1.2, 1.1, 1],
    lineup_score_p10: 100,
    lineup_score_p50: 150,
    lineup_score_p90: 200,
    per_player: [11, 22, 33, 44, 55].map(projection),
    ...overrides,
  };
}

function expectRows(lineup: FrozenLineupPayload) {
  const result = resolveOrderedLineup(lineup);
  expect(result.ok).toBe(true);
  if (!result.ok) throw new Error(result.error);
  return result.rows;
}

describe("resolveOrderedLineup", () => {
  it("uses player_ids as committed order and aligns projections by ID", () => {
    const perPlayer = [55, 33, 11, 44, 22].map(projection);
    const rows = expectRows(payload({ per_player: perPlayer }));

    expect(rows.map((row) => row.player.player_id)).toEqual([
      11, 22, 33, 44, 55,
    ]);
    expect(rows.map((row) => row.slotMultiplier)).toEqual([
      1.5, 1.3, 1.2, 1.1, 1,
    ]);
    expect(rows[0].player).toBe(perPlayer[2]);
  });

  it.each([
    ["absent", undefined],
    ["empty", []],
  ])("uses legacy placeholders when per_player is %s", (_label, perPlayer) => {
    const rows = expectRows(payload({ per_player: perPlayer }));

    expect(rows.map((row) => row.player.display_name)).toEqual([
      "Player 11",
      "Player 22",
      "Player 33",
      "Player 44",
      "Player 55",
    ]);
    expect(rows.every((row) => row.player.pred_real_score_p50 === 0)).toBe(
      true,
    );
  });

  it.each([
    ["too few IDs", [11, 22, 33, 44]],
    ["duplicate IDs", [11, 22, 33, 44, 44]],
  ])("rejects %s", (_label, playerIds) => {
    expect(resolveOrderedLineup(payload({ player_ids: playerIds })).ok).toBe(
      false,
    );
  });

  it.each([
    ["too few multipliers", [1.5, 1.3, 1.2, 1.1]],
    ["zero multiplier", [1.5, 1.3, 1.2, 1.1, 0]],
    ["negative multiplier", [1.5, 1.3, 1.2, 1.1, -1]],
    ["infinite multiplier", [1.5, 1.3, 1.2, 1.1, Infinity]],
    ["NaN multiplier", [1.5, 1.3, 1.2, 1.1, Number.NaN]],
  ])("rejects %s", (_label, slotMultipliers) => {
    expect(
      resolveOrderedLineup(
        payload({ slot_multipliers: slotMultipliers }),
      ).ok,
    ).toBe(false);
  });

  it.each([
    ["partial projections", [11, 22, 33, 44]],
    ["duplicate projection IDs", [11, 22, 33, 44, 44]],
    ["a mismatched projection ID", [11, 22, 33, 44, 66]],
    ["an extra projection", [11, 22, 33, 44, 55, 66]],
  ])("rejects %s instead of substituting placeholders", (_label, ids) => {
    expect(
      resolveOrderedLineup(payload({ per_player: ids.map(projection) })).ok,
    ).toBe(false);
  });
});

describe("Slip contract error", () => {
  it("renders malformed lineup data as an accessible visible error", () => {
    const lineup: FrozenLineup = {
      slate_date: "2026-08-22",
      model_sha: "model-sha",
      payout_regime: "top_20",
      frozen_at: "2026-08-22T22:20:00Z",
      lineup: payload({ player_ids: [11, 22, 33, 44] }),
      entry_recommendation: "enter",
      expected_payout: 1.2,
      metadata_json: null,
      freeze_seq: 1,
      frozen_via: "job2",
    };

    const html = renderToStaticMarkup(createElement(Slip, { lineup }));

    expect(html).toContain('role="alert"');
    expect(html).toContain('aria-live="assertive"');
    expect(html).toContain("Lineup unavailable");
    expect(html).toContain("This frozen lineup cannot be displayed safely.");
    expect(html).toContain("Expected exactly five unique player IDs.");
    expect(html).not.toContain('aria-label="Five-player frozen lineup, ranked"');
  });
});
