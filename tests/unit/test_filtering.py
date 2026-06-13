"""Tests del filtro transversal por país y tipo (ADR-0018): selección, no inferencia."""

from __future__ import annotations

from titan_eye.analytics.filtering import (
    available_countries,
    available_kinds,
    filter_payload,
)


def _payload() -> dict:
    return {
        "domains": {
            "orbital": [{"id": 1, "country": "", "kind": ""}],
            "aerial": [
                {"id": "A1", "country": "US", "kind": ""},
                {"id": "A2", "country": "FR", "kind": ""},
            ],
            "maritime": [
                {"id": "V1", "country": "US", "kind": "carrier"},
                {"id": "V2", "country": "RU", "kind": "submarine"},
            ],
            "suborbital": [{"id": "B1", "country": "", "kind": "ballistic"}],
            "surface": [{"id": "E1", "country": "UA", "kind": "clash"}],
        },
        "heatmap": [{"lon": 1, "lat": 2, "weight": 0.5}],
        "installations": [
            {"id": "I1", "country": "US", "kind": "air_base"},
            {"id": "I2", "country": "FR", "kind": "nuclear_plant"},
        ],
    }


def test_no_filter_returns_same() -> None:
    p = _payload()
    assert filter_payload(p) is p
    assert filter_payload(p, countries=[], kinds=[]) is p


def test_filter_by_country() -> None:
    f = filter_payload(_payload(), countries=["US"])
    assert {e["id"] for e in f["domains"]["aerial"]} == {"A1"}
    assert {e["id"] for e in f["domains"]["maritime"]} == {"V1"}
    assert {e["id"] for e in f["installations"]} == {"I1"}
    # country vacío (orbital/suborbital) se descarta con filtro de país activo
    assert f["domains"]["orbital"] == []
    assert f["domains"]["suborbital"] == []


def test_filter_by_kind() -> None:
    f = filter_payload(_payload(), kinds=["carrier", "submarine"])
    assert {e["id"] for e in f["domains"]["maritime"]} == {"V1", "V2"}
    assert f["domains"]["aerial"] == []          # kind "" no casa
    assert f["installations"] == []


def test_filter_country_and_kind() -> None:
    f = filter_payload(_payload(), countries=["US"], kinds=["carrier"])
    assert {e["id"] for e in f["domains"]["maritime"]} == {"V1"}
    assert f["domains"]["aerial"] == []          # US pero kind "" no casa carrier


def test_filter_does_not_recompute_heatmap() -> None:
    f = filter_payload(_payload(), countries=["US"])
    assert f["heatmap"] == _payload()["heatmap"]   # heatmap intacto (ADR-0018)


def test_filter_is_a_copy() -> None:
    p = _payload()
    filter_payload(p, countries=["US"])
    assert len(p["domains"]["aerial"]) == 2        # el original no se muta


def test_available_countries_and_kinds_skip_empty() -> None:
    p = _payload()
    assert available_countries(p) == ["FR", "RU", "UA", "US"]
    assert "ballistic" in available_kinds(p) and "carrier" in available_kinds(p)
    assert "" not in available_countries(p) and "" not in available_kinds(p)
