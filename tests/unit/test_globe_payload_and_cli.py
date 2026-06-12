"""Tests del traductor a payload de globo y del núcleo de la CLI (sin red)."""

from __future__ import annotations

from datetime import UTC, datetime

from tests.unit.fixtures_opensky import opensky_payload
from titan_eye.catalog.normalizers.opensky_states import normalize_states
from titan_eye.core.domains import Domain
from titan_eye.core.timebase import FixedClock
from titan_eye.ingestion.artifact import RawArtifact
from titan_eye.ingestion.sources.opensky import OPENSKY_STATES_URL, OpenSkySource
from titan_eye.ingestion.transport import FakeTransport, TransportResponse
from titan_eye.orchestration.cli import run_ingest_aerial
from titan_eye.orchestration.globe_payload import aerial_payload, aerial_states_to_entries

T0 = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)


def _states() -> list:
    art = RawArtifact.seal(
        source_id="opensky.states", domain=Domain.AERIAL,
        request_url="u", fetched_at=T0, payload=opensky_payload(),
    )
    return normalize_states(art)


def test_translator_omits_no_position() -> None:
    entries = aerial_states_to_entries(_states())
    assert len(entries) == 2  # la fila sin posición no se dibuja
    ids = {e["id"] for e in entries}
    assert "ghi789" not in ids


def test_translator_fields() -> None:
    e = next(x for x in aerial_states_to_entries(_states()) if x["id"] == "abc123")
    assert e["callsign"] == "DEMO01"
    assert e["lat"] == 49.5 and e["lon"] == 33.0
    assert e["alt_km"] == 10.5
    assert e["speed_kt"] > 0


def test_aerial_payload_shape() -> None:
    p = aerial_payload(_states())
    assert set(p["domains"]) == {"orbital", "aerial", "suborbital", "surface"}
    assert len(p["domains"]["aerial"]) == 2
    assert p["layers"]["aerial"] is True


def _fake_source() -> OpenSkySource:
    ft = FakeTransport()
    ft.responses[OPENSKY_STATES_URL] = TransportResponse(
        url=OPENSKY_STATES_URL, status=200, body=opensky_payload(), media_type="application/json"
    )
    return OpenSkySource(transport=ft, clock=FixedClock(T0))


def test_cli_ingest_aerial_summary() -> None:
    summary = run_ingest_aerial(source=_fake_source())
    assert summary["domain"] == "aerial"
    assert summary["n_states"] == 3
    assert summary["n_with_position"] == 2
    assert summary["epistemic_label"] == "observed"
    assert "opensky" in summary["license_note"].lower()
    assert len(summary["sample"]) == 2
