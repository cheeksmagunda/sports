"""Compute theoretical ceiling: perfect-projection optimal lineup per slate, and noise sweep.

Scoring formula (verified empirically against winning lineups, see report):
    effective_mult_i = slot_mult_i + card_boost_player_i
    player_points    = real_score_player_i * effective_mult_i
    lineup_score     = sum over 5 chosen (player, slot) pairs of player_points
with slot_mults = [2.0, 1.8, 1.6, 1.4, 1.2] (each slot used exactly once).

For a chosen 5-set, optimal assignment: sort by real_score desc, assign largest
slot_mult to highest real_score (greedy on the slot-only term; the boost-only
term is slot-independent so it does not affect the within-set assignment).

Outputs:
  research/internal/_ceiling_perfect.parquet   (per-slate perfect vs winner)
  research/internal/_ceiling_noise.parquet     (noise sweep curve)
  research/internal/_ceiling_summary.json      (headline aggregates)
"""
from __future__ import annotations
import glob, json, os, itertools
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SLATE_DIR = ROOT / 'data/historical/slate_labels'
LB_DIR    = ROOT / 'data/historical/leaderboards'
OUT_DIR   = ROOT / 'research/internal'

SLOTS = np.array([2.0, 1.8, 1.6, 1.4, 1.2])


def lineup_score(reals: np.ndarray, boosts: np.ndarray) -> float:
    """Realized score for a chosen 5-player set under OPTIMAL slot assignment.

    reals, boosts: length-5 arrays for the chosen players (any order).
    Returns the maximum achievable score across the 5! slot permutations,
    which equals the closed form below (because the boost contribution is
    slot-independent and the slot contribution is maximized by reverse-sorting
    the reals against the descending slot multipliers).
    """
    order = np.argsort(-reals)
    r_sorted = reals[order]
    b_sorted = boosts[order]
    return float(np.dot(r_sorted, SLOTS) + np.dot(r_sorted, b_sorted))


def lineup_score_picker(reals: np.ndarray, boosts: np.ndarray, projections: np.ndarray) -> float:
    """Score when the picker chose 5 players and assigned slots by PROJECTION
    desc. Slot ordering is decided BEFORE outcomes are known.
    """
    order = np.argsort(-projections)
    r_sorted = reals[order]
    b_sorted = boosts[order]
    return float(np.dot(r_sorted, SLOTS) + np.dot(r_sorted, b_sorted))


def perfect_optimal(reals: np.ndarray, boosts: np.ndarray) -> tuple[float, np.ndarray]:
    """Brute-force the best 5-set among `n` players."""
    n = len(reals)
    if n <= 5:
        idx = np.arange(n)
        return lineup_score(reals[idx], boosts[idx]), idx

    best = -1e18
    best_idx = None
    # For each combo, score in closed form
    for combo in itertools.combinations(range(n), 5):
        idx = list(combo)
        s = lineup_score(reals[idx], boosts[idx])
        if s > best:
            best = s
            best_idx = combo
    return best, np.array(best_idx)


def top_k_by_proj(projections: np.ndarray, k: int = 5) -> np.ndarray:
    """Greedy: choose top-5 by projection. (Optimal for the score-only piece;
    not perfectly optimal under boosts since a high-boost mid-projection player
    can beat a higher-projection zero-boost player. We treat this as part of
    the picker's job, modeled by the projection itself which IS the realized
    fantasy points unit.)"""
    return np.argsort(-projections)[:k]


def best_k_by_projected_score(reals_proxy: np.ndarray, boosts: np.ndarray, k: int = 5) -> np.ndarray:
    """A smarter greedy: for each player compute projected contribution
    (real_score * (slot_mult_top + boost)) using slot 2.0 as a tie-breaker,
    then take top-5. Not used in noise sweep; we keep top_k_by_proj as the
    user's picker proxy."""
    contrib = reals_proxy * (2.0 + boosts)  # rough rank
    return np.argsort(-contrib)[:k]


def main():
    slates = sorted(glob.glob(str(SLATE_DIR / 'slate_date=*/data.parquet')))
    rng = np.random.default_rng(20260605)

    rows = []
    perfect_cache: dict[str, dict] = {}
    for sp in slates:
        sl = pd.read_parquet(sp)
        if sl.empty:
            continue
        sdate = sl['slate_date'].iloc[0]
        contest_id = sl['contest_id'].iloc[0]
        reals = sl['real_score'].to_numpy(dtype=float)
        boosts = sl['card_boost'].to_numpy(dtype=float)
        n = len(reals)
        best, best_idx = perfect_optimal(reals, boosts)
        lb_path = LB_DIR / f'slate_date={sdate}/data.parquet'
        if not lb_path.exists():
            continue
        lb = pd.read_parquet(lb_path)
        if lb.empty:
            continue
        nb = int(lb['num_brawlers'].iloc[0])
        scores_sorted = lb.sort_values('rank')['score'].to_numpy()
        top1 = float(scores_sorted[0])
        rank20 = float(scores_sorted[-1])
        # Did winner's lineup overlap with perfect lineup?
        winner_lineup = json.loads(lb.iloc[0]['lineup_json'])
        winner_pids = [p['playerId'] for p in winner_lineup]
        perfect_pids = sl.iloc[best_idx]['platform_player_id'].tolist()
        overlap = len(set(winner_pids) & set(perfect_pids))
        rows.append({
            'slate_date': sdate,
            'contest_id': int(contest_id),
            'num_brawlers': nb,
            'menu_size': n,
            'perfect_score': best,
            'rank1_score': top1,
            'rank20_score': rank20,
            'perfect_beats_rank1': best > top1,
            'perfect_minus_rank1': best - top1,
            'rank1_pct_of_perfect': top1 / best if best > 0 else None,
            'winner_perfect_overlap': overlap,
        })
        perfect_cache[sdate] = {
            'menu_size': n,
            'reals': reals,
            'boosts': boosts,
            'best_idx': best_idx,
            'best_score': best,
            'lb_scores': scores_sorted,
            'num_brawlers': nb,
        }

    perf_df = pd.DataFrame(rows)
    perf_df.to_parquet(OUT_DIR / '_ceiling_perfect.parquet', index=False)
    print('perfect-projection slates:', len(perf_df))
    print('mean perfect:', round(perf_df['perfect_score'].mean(), 2))
    print('mean rank1:  ', round(perf_df['rank1_score'].mean(), 2))
    print('mean rank20: ', round(perf_df['rank20_score'].mean(), 2))
    print('perfect beats rank1 in', int(perf_df['perfect_beats_rank1'].sum()),
          'of', len(perf_df), 'slates')
    print('mean perfect - rank1:', round(perf_df['perfect_minus_rank1'].mean(), 2))
    print('mean rank1 / perfect:', round(perf_df['rank1_pct_of_perfect'].mean(), 3))
    print('overlap dist:', perf_df['winner_perfect_overlap'].value_counts().sort_index().to_dict())

    # --- Noise sweep ---
    sigmas = [0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0]
    N_TRIALS = 1000

    # Per-slate rank model: log(rank) ~ a + b * score, fit on top-20 finishers.
    rank_models: dict[str, tuple[float, float]] = {}
    for sdate, info in perfect_cache.items():
        sc = info['lb_scores']
        ranks = np.arange(1, len(sc) + 1, dtype=float)
        if len(sc) >= 3 and np.std(sc) > 1e-6:
            y = np.log(ranks)
            X = sc
            b, a = np.polyfit(X, y, 1)
            # clamp b to negative for monotonicity
            if b >= 0:
                b = -0.05
        else:
            a, b = np.log(10.0), -0.05
        rank_models[sdate] = (float(a), float(b))

    def implied_rank(sdate: str, score: float) -> float:
        a, b = rank_models[sdate]
        nb = perfect_cache[sdate]['num_brawlers']
        # numerically stable
        log_r = a + b * score
        log_r = np.clip(log_r, 0.0, np.log(nb))
        return float(np.exp(log_r))

    noise_rows = []
    for sigma in sigmas:
        slate_mean = []
        slate_median = []
        slate_top500 = []
        slate_top20 = []
        slate_win = []
        slate_pct_perfect = []
        for sdate, info in perfect_cache.items():
            reals = info['reals']
            boosts = info['boosts']
            n = len(reals)
            if n < 5:
                continue
            ranks_this = []
            scores_this = []
            for _ in range(N_TRIALS):
                proj = reals + rng.normal(0.0, sigma, size=n)
                # Picker uses projection-derived contribution (proj * (2.0 + boost))
                # to choose 5 — this models the live picker which considers boost.
                contrib = proj * (2.0 + boosts)
                idx = np.argsort(-contrib)[:5]
                s = lineup_score_picker(reals[idx], boosts[idx], proj[idx])
                scores_this.append(s)
                ranks_this.append(implied_rank(sdate, s))
            ranks_this = np.asarray(ranks_this)
            scores_this = np.asarray(scores_this)
            slate_mean.append(ranks_this.mean())
            slate_median.append(np.median(ranks_this))
            slate_top500.append(float(np.mean(ranks_this <= 500)))
            slate_top20.append(float(np.mean(ranks_this <= 20)))
            slate_win.append(float(np.mean(ranks_this <= 1.5)))
            if info['best_score'] > 0:
                slate_pct_perfect.append(float(scores_this.mean() / info['best_score']))
        noise_rows.append({
            'sigma': sigma,
            'mean_rank': float(np.mean(slate_mean)),
            'median_rank': float(np.median(slate_median)),
            'top500_rate': float(np.mean(slate_top500)),
            'top20_rate': float(np.mean(slate_top20)),
            'win_rate': float(np.mean(slate_win)),
            'score_pct_of_perfect': float(np.mean(slate_pct_perfect)) if slate_pct_perfect else None,
        })
        print(f'sigma={sigma:5.2f}  mean_rank={noise_rows[-1]["mean_rank"]:7.0f}  '
              f'top500={noise_rows[-1]["top500_rate"]*100:5.1f}%  '
              f'top20={noise_rows[-1]["top20_rate"]*100:5.2f}%  '
              f'win={noise_rows[-1]["win_rate"]*100:5.2f}%  '
              f'%perfect={noise_rows[-1]["score_pct_of_perfect"]*100:5.1f}%')

    noise_df = pd.DataFrame(noise_rows)
    noise_df.to_parquet(OUT_DIR / '_ceiling_noise.parquet', index=False)

    # Implied RMSE from corr (assuming similar variances)
    all_rs = pd.concat([pd.read_parquet(p)['real_score'] for p in slates])
    sigma_y = float(all_rs.std())
    rmse_heads = sigma_y * np.sqrt(2 * (1 - 0.554))
    rmse_heur  = sigma_y * np.sqrt(2 * (1 - 0.246))
    print()
    print(f'sigma_y = {sigma_y:.3f}')
    print(f'RMSE heads (corr=0.554) ~ {rmse_heads:.3f}')
    print(f'RMSE heuristic (corr=0.246) ~ {rmse_heur:.3f}')

    summary = {
        'num_slates': int(len(perf_df)),
        'mean_perfect_score': float(perf_df['perfect_score'].mean()),
        'median_perfect_score': float(perf_df['perfect_score'].median()),
        'mean_rank1_score': float(perf_df['rank1_score'].mean()),
        'mean_rank20_score': float(perf_df['rank20_score'].mean()),
        'perfect_beats_rank1_count': int(perf_df['perfect_beats_rank1'].sum()),
        'perfect_beats_rank1_rate': float(perf_df['perfect_beats_rank1'].mean()),
        'mean_perfect_minus_rank1': float(perf_df['perfect_minus_rank1'].mean()),
        'median_perfect_minus_rank1': float(perf_df['perfect_minus_rank1'].median()),
        'mean_rank1_pct_of_perfect': float(perf_df['rank1_pct_of_perfect'].mean()),
        'overlap_dist': perf_df['winner_perfect_overlap'].value_counts().sort_index().to_dict(),
        'sigma_y_real_score': sigma_y,
        'rmse_heads_implied': rmse_heads,
        'rmse_heuristic_implied': rmse_heur,
        'noise_sweep': noise_rows,
    }
    with open(OUT_DIR / '_ceiling_summary.json', 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    print('summary written to', OUT_DIR / '_ceiling_summary.json')


if __name__ == '__main__':
    main()
