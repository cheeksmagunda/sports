"""D69 / Phase 2b: the D63 trained-head Tier-0 path in job2._build_specs.

The Tier-0 path is PURELY ADDITIVE: when the loaded artifact has a (minutes, F)
+ (real_score_per_min, F) pair AND a pool player has ``head_features`` persisted
in ``features_json``, predict_real_score recomposes p10/p50/p90 and the per-row
loop short-circuits the legacy ladder. Every other code path (no artifact heads,
missing head_features row, predict raise) must fall through to the existing
blended_real_score / EB / heuristic chain byte-for-byte.

These four tests pin the four branches.
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np

from wnba_oracle.picker.popularity import ContrarianConfig
from wnba_oracle.scheduler import job2

HEAD_COLS = (
    "days_rest",
    "is_back_to_back",
    "season_game_number",
    "mins_l5",
    "mins_l10",
    "mins_l20",
    "fantasy_pts_l5",
    "fantasy_pts_l10",
    "pts_per_min_l5",
    "pts_per_min_l10",
    "reb_per_min_l10",
    "ast_per_min_l10",
    "stl_blk_per_min_l10",
    "ts_pct_l10",
    "efg_pct_l10",
    "usg_pct_l10",
    "ast_to_tov_l10",
    "fg3_pct_l10",
    "plus_minus_l10",
    "foul_rate_l10",
    "coach_rotation_consistency_l20",
)


def _head_feature_row(**overrides: float) -> dict[str, float]:
    base = dict.fromkeys(HEAD_COLS, 1.0)
    base.update(overrides)
    return base


def _enrich(
    pid: int,
    *,
    with_head_features: bool,
    boost: float = 2.0,
    rotowire_confirmed: int = 0,
    is_starter: int = 0,
) -> dict:
    features: dict[str, Any] = {}
    if with_head_features:
        features["head_features"] = _head_feature_row()
    if rotowire_confirmed:
        features["rotowire_confirmed"] = rotowire_confirmed
        features["is_starter"] = is_starter
    return {
        "real_sports_player_id": str(pid),
        "name": f"Pool Player {pid}",
        "team": "LV",
        "opponent": "NYL",
        "position": "F",
        "card_boost": boost,
        "features_json": json.dumps(features),
    }


class _FakeHead:
    def __init__(self) -> None:
        self.feature_columns = HEAD_COLS


class _FakeArtifact:
    def __init__(self, *, with_heads: bool, predict_returns: Any = "default") -> None:
        if with_heads:
            self.heads = {("minutes", "F"): _FakeHead(), ("real_score_per_min", "F"): _FakeHead()}
        else:
            self.heads = {}
        # _eb_predict_one in job2 reaches for art.eb_baseline; stay None so the
        # ladder takes its corpus-history / heuristic fall-through branch.
        self.eb_baseline = None
        self._predict_returns = predict_returns
        self.predict_calls: list[int] = []

    def predict_real_score(self, frame: Any) -> Any:
        self.predict_calls.append(len(frame))
        if self._predict_returns == "default":
            n = len(frame)
            return {
                "p10": np.array([3.0] * n),
                "p50": np.array([7.5] * n),
                "p90": np.array([14.0] * n),
            }
        if self._predict_returns == "raise":
            raise RuntimeError("boom")
        return self._predict_returns


def _common_patch(monkeypatch, art: _FakeArtifact | None) -> None:
    monkeypatch.setattr(job2, "_load_model_artifact", lambda *_a, **_k: art)
    monkeypatch.setattr(job2, "_load_measured_drafts", lambda *_a, **_k: {})
    monkeypatch.setattr(job2, "_load_slate_label_names", lambda *_a, **_k: {})


def test_tier0_fires_when_heads_and_features_present(monkeypatch) -> None:
    """Heads + head_features -> Tier-0 prediction lands in projection_by_pid."""
    art = _FakeArtifact(with_heads=True)
    _common_patch(monkeypatch, art)
    enrichment = [_enrich(101, with_head_features=True)]
    _samps, _fields, proj = job2._build_specs(
        enrichment,
        slate_date="2026-06-06",
        contrarian_cfg=ContrarianConfig(enabled=False, strength=0.0),
    )
    assert art.predict_calls, "predict_real_score never called"
    p = proj[101]
    # p50 7.5 floored at 0.5, no game-script (Vegas total 0 -> 1.0x) so passthrough.
    assert p["pred_real_score_p50"] == 7.5
    assert p["pred_real_score_p10"] == 3.0
    assert p["pred_real_score_p90"] == 14.0


def test_tier0_skips_when_artifact_missing_heads(monkeypatch) -> None:
    """Artifact without (minutes,F)+(rate,F) -> Tier-0 silent, no p10/p90 surfaced."""
    art = _FakeArtifact(with_heads=False)
    _common_patch(monkeypatch, art)
    enrichment = [_enrich(202, with_head_features=True)]
    _samps, _fields, proj = job2._build_specs(
        enrichment,
        slate_date="2026-06-06",
        contrarian_cfg=ContrarianConfig(enabled=False, strength=0.0),
    )
    assert not art.predict_calls
    assert "pred_real_score_p10" not in proj[202]
    # Heuristic still fills pred_real_score_p50 (the legacy ladder path).
    assert proj[202]["pred_real_score_p50"] > 0


def test_tier0_skips_when_no_head_features_row(monkeypatch) -> None:
    """Pool player without features_json.head_features -> Tier-0 silent."""
    art = _FakeArtifact(with_heads=True)
    _common_patch(monkeypatch, art)
    enrichment = [_enrich(303, with_head_features=False)]
    _samps, _fields, proj = job2._build_specs(
        enrichment,
        slate_date="2026-06-06",
        contrarian_cfg=ContrarianConfig(enabled=False, strength=0.0),
    )
    # Heads exist but the enrichment built no rows -> predict not called.
    assert not art.predict_calls
    assert "pred_real_score_p10" not in proj[303]


def test_tier0_swallows_predict_failure(monkeypatch) -> None:
    """If predict_real_score raises, ladder still serves the freeze."""
    art = _FakeArtifact(with_heads=True, predict_returns="raise")
    _common_patch(monkeypatch, art)
    enrichment = [_enrich(404, with_head_features=True)]
    _samps, _fields, proj = job2._build_specs(
        enrichment,
        slate_date="2026-06-06",
        contrarian_cfg=ContrarianConfig(enabled=False, strength=0.0),
    )
    assert art.predict_calls  # was called
    assert "pred_real_score_p10" not in proj[404]
    assert proj[404]["pred_real_score_p50"] > 0


# D71 / R5: the head Tier-0 path applies the RotoWire confirmed-starter
# multiplier symmetrically to all three quantiles, matching the Tier-3
# fallback's use of `_starter_multiplier`. The trained head learned without
# `is_confirmed_starter` (it's not in the gamelog corpus), so this nudge
# restores the same-day starter signal at serve time. Magnitudes:
#   - confirmed starter (rotowire_confirmed=1, is_starter=1) -> 1.10
#   - confirmed bench   (rotowire_confirmed=1, is_starter=0) -> 0.82
#   - unmatched         (rotowire_confirmed=0)               -> 1.00
# These three tests pin all three magnitudes against the same base p50/p10/p90
# (7.5 / 3.0 / 14.0 from _FakeArtifact.predict_real_score).


def test_tier0_confirmed_starter_scales_quantiles_up(monkeypatch) -> None:
    art = _FakeArtifact(with_heads=True)
    _common_patch(monkeypatch, art)
    enrichment = [_enrich(501, with_head_features=True, rotowire_confirmed=1, is_starter=1)]
    _samps, _fields, proj = job2._build_specs(
        enrichment,
        slate_date="2026-06-06",
        contrarian_cfg=ContrarianConfig(enabled=False, strength=0.0),
    )
    p = proj[501]
    assert p["pred_real_score_p50"] == 7.5 * 1.10
    assert p["pred_real_score_p10"] == 3.0 * 1.10
    assert p["pred_real_score_p90"] == 14.0 * 1.10


def test_tier0_confirmed_bench_scales_quantiles_down(monkeypatch) -> None:
    art = _FakeArtifact(with_heads=True)
    _common_patch(monkeypatch, art)
    enrichment = [_enrich(502, with_head_features=True, rotowire_confirmed=1, is_starter=0)]
    _samps, _fields, proj = job2._build_specs(
        enrichment,
        slate_date="2026-06-06",
        contrarian_cfg=ContrarianConfig(enabled=False, strength=0.0),
    )
    p = proj[502]
    assert p["pred_real_score_p50"] == 7.5 * 0.82
    assert p["pred_real_score_p10"] == 3.0 * 0.82
    assert p["pred_real_score_p90"] == 14.0 * 0.82


def test_tier0_unmatched_player_unchanged(monkeypatch) -> None:
    art = _FakeArtifact(with_heads=True)
    _common_patch(monkeypatch, art)
    enrichment = [_enrich(503, with_head_features=True)]  # rotowire_confirmed default 0
    _samps, _fields, proj = job2._build_specs(
        enrichment,
        slate_date="2026-06-06",
        contrarian_cfg=ContrarianConfig(enabled=False, strength=0.0),
    )
    p = proj[503]
    assert p["pred_real_score_p50"] == 7.5
    assert p["pred_real_score_p10"] == 3.0
    assert p["pred_real_score_p90"] == 14.0
