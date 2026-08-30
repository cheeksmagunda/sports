"""#35 phase 3 / #39: read-only dossier API surface.

/dossier/{slate_date} composes the canonical committed/field-winner/
theoretical-ceiling records via wnba_oracle.dossier.build_dossier rather
than recalculating history; this only tests the route's wiring (engine
construction, 404/503 mapping, response serialization) since build_dossier
itself is covered by test_dossier.py.
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient
from oracle_core import CensoringReason, Dossier, DossierEntry, EntryKind, Exactness, Gap

from wnba_oracle.api.app import app

_DOSSIER = Dossier(
    slate_date="2026-06-08",
    entries={
        EntryKind.COMMITTED: DossierEntry(
            kind=EntryKind.COMMITTED,
            score=100.0,
            achievable=True,
            slot_order_basis="committed",
        ),
        EntryKind.FIELD_BEST: DossierEntry(
            kind=EntryKind.FIELD_BEST,
            score=110.0,
            achievable=True,
            slot_order_basis="as_entered",
        ),
        EntryKind.THEORETICAL_CEILING: DossierEntry(
            kind=EntryKind.THEORETICAL_CEILING,
            score=130.0,
            achievable=False,
            slot_order_basis="optimal_resort",
        ),
    },
    gap_to_field=Gap(
        from_kind=EntryKind.COMMITTED,
        to_kind=EntryKind.FIELD_BEST,
        value=10.0,
        exactness=Exactness.EXACT,
    ),
    gap_field_to_ceiling=Gap(
        from_kind=EntryKind.FIELD_BEST,
        to_kind=EntryKind.THEORETICAL_CEILING,
        value=20.0,
        exactness=Exactness.LOWER_BOUND,
    ),
    gap_to_ceiling=Gap(
        from_kind=EntryKind.COMMITTED,
        to_kind=EntryKind.THEORETICAL_CEILING,
        value=30.0,
        exactness=Exactness.LOWER_BOUND,
    ),
)


def test_returns_dossier_payload_when_available() -> None:
    with (
        patch("wnba_oracle.api.dossier.get_engine", return_value="fake-engine"),
        patch("wnba_oracle.api.dossier.build_dossier", return_value=_DOSSIER) as mock_build,
    ):
        resp = TestClient(app).get("/dossier/2026-06-08")

    assert resp.status_code == 200
    body = resp.json()
    assert body["slate_date"] == "2026-06-08"
    assert body["entries"]["theoretical_ceiling"]["achievable"] is False
    assert body["gap_field_to_ceiling"]["exactness"] == "lower_bound"
    assert body["gap_to_ceiling"]["exactness"] == "lower_bound"
    mock_build.assert_called_once_with("2026-06-08", engine="fake-engine")


def test_404_when_dossier_cannot_be_built() -> None:
    with (
        patch("wnba_oracle.api.dossier.get_engine", return_value="fake-engine"),
        patch("wnba_oracle.api.dossier.build_dossier", return_value=None),
    ):
        resp = TestClient(app).get("/dossier/2026-06-08")

    assert resp.status_code == 404


def test_503_when_engine_is_unavailable() -> None:
    with patch(
        "wnba_oracle.api.dossier.get_engine", side_effect=RuntimeError("no database configured")
    ):
        resp = TestClient(app).get("/dossier/2026-06-08")

    assert resp.status_code == 503


def test_censored_ceiling_serializes_censor_reason() -> None:
    censored = Dossier(
        slate_date="2026-06-08",
        entries={**_DOSSIER.entries},
        gap_to_field=_DOSSIER.gap_to_field,
        gap_field_to_ceiling=Gap(
            from_kind=EntryKind.FIELD_BEST,
            to_kind=EntryKind.THEORETICAL_CEILING,
            value=20.0,
            exactness=Exactness.LOWER_BOUND,
            to_censor=CensoringReason.INCOMPLETE_LABELS,
        ),
        gap_to_ceiling=_DOSSIER.gap_to_ceiling,
    )
    with (
        patch("wnba_oracle.api.dossier.get_engine", return_value="fake-engine"),
        patch("wnba_oracle.api.dossier.build_dossier", return_value=censored),
    ):
        resp = TestClient(app).get("/dossier/2026-06-08")

    assert resp.status_code == 200
    assert resp.json()["gap_field_to_ceiling"]["to_censor"] == "incomplete_labels"
