"""Tests de proximidad geométrica multidominio (ADR-0014): geometría sin veredictos."""

from __future__ import annotations

import pytest

from titan_eye.analytics.proximity import (
    PositionedEntity,
    entities_from_payload,
    find_proximities,
)
from titan_eye.core.domains import Domain
from titan_eye.core.epistemics import EpistemicLabel
from titan_eye.core.errors import AnalyticsError

OBS = EpistemicLabel.OBSERVED
INF = EpistemicLabel.INFERRED
ASS = EpistemicLabel.ASSERTED


def _e(domain, eid, lat, lon, alt, ep, unc) -> PositionedEntity:
    return PositionedEntity(domain, eid, lat, lon, alt, ep, unc)


def test_finds_near_pair() -> None:
    ents = [
        _e(Domain.AERIAL, "A", 48.00, 37.60, 10.0, OBS, 0.5),
        _e(Domain.SURFACE, "B", 48.05, 37.62, 0.0, ASS, 12.0),   # ~6 km
        _e(Domain.AERIAL, "C", 10.0, 10.0, 10.0, OBS, 0.5),       # lejos
    ]
    evs = find_proximities(ents, horizontal_threshold_km=20.0)
    assert len(evs) == 1
    ev = evs[0]
    assert {ev.a_id, ev.b_id} == {"A", "B"}
    assert ev.horizontal_distance_km < 20.0


def test_horizontal_and_vertical_reported_separately() -> None:
    # Satélite a 400 km sobre una aeronave: cerca en tierra, lejísimos en vertical.
    ents = [
        _e(Domain.ORBITAL, "SAT", 48.0, 37.6, 400.0, OBS, 2.0),
        _e(Domain.AERIAL, "AIR", 48.0, 37.6, 10.0, OBS, 0.5),
    ]
    ev = find_proximities(ents, horizontal_threshold_km=5.0)[0]
    assert ev.horizontal_distance_km == pytest.approx(0.0, abs=0.1)
    assert ev.vertical_separation_km == pytest.approx(390.0, abs=0.1)


def test_combined_uncertainty() -> None:
    ents = [
        _e(Domain.AERIAL, "A", 48.0, 37.6, 10.0, OBS, 3.0),
        _e(Domain.AERIAL, "B", 48.01, 37.6, 10.0, OBS, 4.0),
    ]
    ev = find_proximities(ents, horizontal_threshold_km=10.0)[0]
    assert ev.combined_uncertainty_km == pytest.approx(5.0, abs=1e-6)  # hypot(3,4)


def test_inherits_weakest_epistemic() -> None:
    ents = [
        _e(Domain.AERIAL, "A", 48.0, 37.6, 10.0, OBS, 0.5),
        _e(Domain.SUBORBITAL, "BAL", 48.02, 37.6, 0.0, INF, 30.0),
    ]
    ev = find_proximities(ents, horizontal_threshold_km=10.0)[0]
    assert ev.weakest_epistemic is INF        # observed + inferred -> inferred
    assert ev.cross_domain is True


def test_no_verdict_only_geometry() -> None:
    import dataclasses
    ents = [
        _e(Domain.AERIAL, "A", 48.0, 37.6, 10.0, OBS, 0.5),
        _e(Domain.SURFACE, "B", 48.0, 37.61, 0.0, ASS, 12.0),
    ]
    ev = find_proximities(ents, horizontal_threshold_km=10.0)[0]
    # Ningún CAMPO de amenaza/intención/riesgo/score: solo geometría + procedencia.
    field_names = {f.name.lower() for f in dataclasses.fields(ev)}
    banned = ("threat", "amenaza", "intent", "intenc", "risk", "riesgo", "score", "hostil")
    assert not any(w in name for name in field_names for w in banned)
    # La nota declara explícitamente que NO implica intención/amenaza.
    assert "no implica intención" in ev.note.lower()


def test_cross_domain_only() -> None:
    ents = [
        _e(Domain.AERIAL, "A", 48.0, 37.6, 10.0, OBS, 0.5),
        _e(Domain.AERIAL, "B", 48.0, 37.61, 10.0, OBS, 0.5),   # mismo dominio
        _e(Domain.SURFACE, "C", 48.0, 37.6, 0.0, ASS, 12.0),
    ]
    evs = find_proximities(ents, horizontal_threshold_km=10.0, same_domain=False)
    assert all(e.cross_domain for e in evs)
    assert all({e.a_domain, e.b_domain} != {Domain.AERIAL} for e in evs)


def test_threshold_rejects_invalid() -> None:
    with pytest.raises(AnalyticsError):
        find_proximities([], horizontal_threshold_km=0)


def test_entities_from_payload() -> None:
    payload = {
        "domains": {
            "aerial": [{"id": "AIR1", "lat": 48.0, "lon": 37.6, "alt_km": 10.0}],
            "orbital": [{"id": 25544, "lat": 1.0, "lon": 2.0, "alt_km": 420.0, "err_km": 2.3}],
            "surface": [{"id": "E1", "lat": 48.0, "lon": 37.6, "geoloc_res": "region"}],
            "suborbital": [{"id": "BAL", "impact": [139.0, 35.0], "impact_dispersion_km": 40}],
        }
    }
    ents = {e.entity_id: e for e in entities_from_payload(payload)}
    assert len(ents) == 4
    assert ents["E1"].epistemic_label is ASS
    assert ents["E1"].position_uncertainty_km == 55.0   # region
    assert ents["BAL"].epistemic_label is INF
    assert ents["BAL"].latitude == 35.0 and ents["BAL"].longitude == 139.0
    assert ents["25544"].position_uncertainty_km == 2.3
