"""Tests del parser de mensajes AISStream -> fila para normalize_ais (puro, sin red)."""

from __future__ import annotations

from titan_eye.ingestion.sources.aisstream import aisstream_message_to_vessel

_MSG = {
    "MessageType": "PositionReport",
    "MetaData": {"MMSI": 211234560, "ShipName": "  TEST VESSEL  ",
                 "latitude": 36.5, "longitude": -5.3, "time_utc": "2026-06-14 08:00:00"},
    "Message": {"PositionReport": {"Cog": 90.5, "Sog": 12.3, "TrueHeading": 88,
                                   "NavigationalStatus": 0, "Latitude": 36.5, "Longitude": -5.3}},
}


def test_parses_position_report() -> None:
    v = aisstream_message_to_vessel(_MSG)
    assert v is not None
    assert v["mmsi"] == "211234560"
    assert v["name"] == "TEST VESSEL"          # recortado
    assert v["latitude"] == 36.5
    assert v["course"] == 90.5
    assert v["heading"] == 88.0
    assert v["speed"] == 12.3
    assert v["nav_status"] == "en navegación (motor)"


def test_heading_511_means_unavailable() -> None:
    msg = {**_MSG, "Message": {"PositionReport": {**_MSG["Message"]["PositionReport"],
                                                  "TrueHeading": 511}}}
    v = aisstream_message_to_vessel(msg)
    assert v is not None
    assert v["heading"] is None


def test_non_position_message_ignored() -> None:
    assert aisstream_message_to_vessel({"MessageType": "ShipStaticData"}) is None
    assert aisstream_message_to_vessel({}) is None
    assert aisstream_message_to_vessel("nope") is None


def test_missing_coords_ignored() -> None:
    msg = {"MessageType": "PositionReport", "MetaData": {"MMSI": 1}, "Message": {}}
    assert aisstream_message_to_vessel(msg) is None


def test_output_is_consumable_by_ais_normalizer() -> None:
    # Las claves de salida deben casar con lo que normalize_ais espera.
    import json
    from datetime import UTC, datetime

    from titan_eye.catalog.normalizers.ais import normalize_ais
    from titan_eye.core.domains import Domain
    from titan_eye.core.epistemics import EpistemicLabel
    from titan_eye.ingestion.artifact import RawArtifact

    v = aisstream_message_to_vessel(_MSG)
    payload = json.dumps({"vessels": [v]}).encode()
    art = RawArtifact.seal(
        source_id="aisstream.v0", domain=Domain.MARITIME, request_url="wss://x",
        fetched_at=datetime(2026, 6, 14, tzinfo=UTC), payload=payload,
        epistemic_label=EpistemicLabel.OBSERVED,
    )
    vessels = normalize_ais(art)
    assert len(vessels) == 1
    assert vessels[0].mmsi == "211234560"
