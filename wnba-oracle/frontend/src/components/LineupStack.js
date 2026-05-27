import { jsxs as _jsxs, jsx as _jsx } from "react/jsx-runtime";
import { PlayerCard } from "./PlayerCard";
export function LineupStack({ lineup }) {
    const projections = lineup.lineup.per_player ?? [];
    const ids = lineup.lineup.player_ids;
    const mults = lineup.lineup.slot_multipliers;
    // Fallback when API hasn't joined per-player projections yet.
    const cards = projections.length === ids.length
        ? projections
        : ids.map((pid) => ({
            player_id: pid,
            display_name: `Player ${pid}`,
            team: "—",
            opponent: "—",
            position: "F",
            card_boost: 0,
            pred_real_score_p50: 0,
            pred_minutes_p10: 0,
            pred_minutes_p50: 0,
            pred_minutes_p90: 0,
        }));
    return (_jsxs("div", { children: [_jsxs("p", { className: "slate-meta", style: { marginTop: 8 }, children: ["EV ", lineup.expected_payout.toFixed(2), " \u00B7", " ", "lineup P10 / P50 / P90:", " ", lineup.lineup.lineup_score_p10.toFixed(1), " /", " ", lineup.lineup.lineup_score_p50.toFixed(1), " /", " ", lineup.lineup.lineup_score_p90.toFixed(1), " \u00B7", " ", "regime ", lineup.payout_regime] }), _jsx("div", { className: "lineup-stack", children: cards.map((p, idx) => (_jsx(PlayerCard, { slotMultiplier: mults[idx] ?? 0, slotRank: idx + 1, player: p }, p.player_id))) })] }));
}
