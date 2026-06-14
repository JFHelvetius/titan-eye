"""Tests de la heurística de clasificación militar del dominio aéreo.

La heurística es pública y determinista; estos tests fijan su contrato y su
honestidad (es una INFERENCIA, no un dato verificado)."""

from __future__ import annotations

from titan_eye.analytics.military_filter import (
    MILITARY_CALLSIGN_PREFIXES,
    MILITARY_ICAO24_RANGES,
    military_match,
)


def test_callsign_prefix_matches() -> None:
    assert military_match("RCH123", None) is not None
    assert "USAF" in military_match("RCH123", None)
    assert military_match("RRR2145", None) is not None  # Royal Air Force


def test_callsign_ignores_case_and_spaces() -> None:
    assert military_match("rch 999", None) == military_match("RCH999", None)


def test_icao24_range_matches() -> None:
    # 0xADF7C8–0xAFFFFF es el bloque militar de EE. UU.
    assert military_match(None, "AE1234") is not None
    assert "US" in military_match(None, "AE1234")


def test_civilian_is_not_flagged() -> None:
    # Indicativo de aerolínea + ICAO24 civil típico → None.
    assert military_match("RYR4XP", "4CA123") is None
    assert military_match("IBE6253", "342315") is None


def test_no_data_returns_none() -> None:
    assert military_match(None, None) is None
    assert military_match("", "") is None


def test_bad_icao24_does_not_raise() -> None:
    assert military_match(None, "ZZZZ") is None  # no es hex


def test_callsign_and_icao_combined_reason() -> None:
    reason = military_match("RCH123", "AE1234")
    assert "·" in reason  # combina ambas señales


def test_tables_are_nonempty_and_well_formed() -> None:
    assert MILITARY_CALLSIGN_PREFIXES
    for lo, hi, country in MILITARY_ICAO24_RANGES:
        assert lo <= hi
        assert isinstance(country, str) and country
