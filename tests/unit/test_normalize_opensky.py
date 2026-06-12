"""Tests del normalizador puro OpenSky -> AircraftState."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tests.unit.fixtures_opensky import OPENSKY_TIME, opensky_payload
from titan_eye.catalog.normalizers.opensky_states import normalize_states
from titan_eye.core.domains import Domain
from titan_eye.core.epistemics import EpistemicLabel
from titan_eye.core.errors import NormalizationError
from titan_eye.core.identity import content_hash_bytes
from titan_eye.ingestion.artifact import RawArtifact

T0 = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)


def _artifact(payload: bytes = b"") -> RawArtifact:
    payload = payload or opensky_payload()
    return RawArtifact.seal(
        source_id="opensky.states", domain=Domain.AERIAL,
        request_url="u", fetched_at=T0, payload=payload,
        epistemic_label=EpistemicLabel.OBSERVED,
    )


def test_normalize_returns_all_rows_including_no_position() -> None:
    states = normalize_states(_artifact())
    assert len(states) == 3  # incluye la fila sin posición (honestidad P2)
    with_pos = [s for s in states if s.has_position]
    assert len(with_pos) == 2


def test_fields_mapped_correctly() -> None:
    states = normalize_states(_artifact())
    a = next(s for s in states if s.icao24 == "abc123")
    assert a.callsign == "DEMO01"  # trim del padding de OpenSky
    assert a.latitude == 49.5 and a.longitude == 33.0
    assert a.position_source == "ADS-B"
    assert a.altitude_km == pytest.approx(10.5, abs=0.001)  # usa geo_altitude
    assert a.epistemic_label is EpistemicLabel.OBSERVED


def test_provenance_fk_is_source_hash() -> None:
    art = _artifact()
    states = normalize_states(art)
    assert all(s.content_hash_source == art.content_hash for s in states)
    assert art.content_hash == content_hash_bytes(opensky_payload())


def test_position_source_mlat_preserved() -> None:
    states = normalize_states(_artifact())
    b = next(s for s in states if s.icao24 == "def456")
    assert b.position_source == "MLAT"


def test_last_contact_age_computed() -> None:
    states = normalize_states(_artifact())
    a = next(s for s in states if s.icao24 == "abc123")
    # time_position = OPENSKY_TIME - 4, snapshot = OPENSKY_TIME -> age 4 s
    assert a.last_contact_age_s == 4.0
    assert a.snapshot_time.timestamp() == OPENSKY_TIME


def test_no_position_row_has_nulls_not_fabricated() -> None:
    states = normalize_states(_artifact())
    c = next(s for s in states if s.icao24 == "ghi789")
    assert c.latitude is None and c.longitude is None
    assert c.on_ground is True
    assert c.altitude_km is None


def test_malformed_payload_raises_normalization_error() -> None:
    with pytest.raises(NormalizationError):
        normalize_states(_artifact(b"not json"))


def test_missing_states_key_raises() -> None:
    with pytest.raises(NormalizationError):
        normalize_states(_artifact(b'{"time": 1}'))


def test_determinism() -> None:
    art = _artifact()
    a = normalize_states(art)
    b = normalize_states(art)
    assert [s.model_dump() for s in a] == [s.model_dump() for s in b]
